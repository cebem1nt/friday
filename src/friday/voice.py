from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Optional

from src.shared import parse_duration
from src import config, log
from sounddevice import RawOutputStream

import numpy as np
import sounddevice as sd
import re, os, threading, time, gc

def record_audio(
    samplerate: int = 16000, 
    channels: int = 1, 
    dtype: str = "float32"
) -> tuple[Future, Callable]:
    chunks = []
    stop_event = threading.Event()
    future = Future()

    def callback(indata, _frames, _time, _status):
        chunks.append(indata.copy())

    def record():
        try:
            with sd.InputStream(
                samplerate=samplerate,
                channels=channels,
                dtype=dtype,
                callback=callback,
            ):
                stop_event.wait()

            audio = np.concatenate(chunks).flatten()
            future.set_result(audio)
        except Exception as exc:
            future.set_exception(exc)

    threading.Thread(target=record, daemon=True).start()
    return future, stop_event.set

class SpeechFilter:
    def __init__(self):
        self.in_code_block = False
        self.pending_fence = ""

    def apply(self, text: str):
        out = self.remove_code_blocks(text)
        out = out.replace("*", "")
        out = out.replace("#", "")

        return out

    def remove_code_blocks(self, text: str):
        data = self.pending_fence + text
        self.pending_fence = ""
        output = []
        i = 0

        while i < len(data):
            if data.startswith("```", i):
                self.in_code_block = not self.in_code_block
                i += 3
                continue

            if data[i] == "`" and len(data) - i < 3:
                self.pending_fence = data[i:]
                break

            if not self.in_code_block:
                output.append(data[i])
            i += 1

        return "".join(output)

class KokoroWrapper:
    def __init__(self):
        self.model = None
        self.last_used = time.monotonic()
        self.unload_after = config.get("tts", "unload_after", parse_duration)
        self.language = config.get("tts", "language")
        self.voice = config.get("tts", "voice")
        self.speed = config.get("tts", "speed", float)

        if config.get("tts", "preload", bool):
            self.__init_model()

        # Audio chunks are tagged with a generation number. stop_speaking()
        # changes the generation, making old queued chunks invalid.
        self.generation = 0
        self.is_speaking = False

        self._speech_buffer = ""
        self._speech_executor = ThreadPoolExecutor(max_workers=1)
        
        self._output_stream = RawOutputStream(
            samplerate=24000,
            channels=1,
            dtype="float32",
        )

        self._output_stream.start()
        self._output_lock = threading.Lock()

    def __init_model(self):
        log.info("Initializing kokoro...")

        if config.get("tts", "prefer_cpu", bool):
            log.debug("KokoroWrapper: prefer_cpu is set, CPUExecutionProvider will be used")
            os.environ["ONNX_PROVIDER"] = "CPUExecutionProvider"

        from kokoro_onnx import Kokoro

        self.g2p = None

        if not self.language.startswith("en"):
            log.debug("KokoroWrapper: not english language, phonemizer will be used")
            from misaki.espeak import EspeakG2P

            self.g2p = EspeakG2P(language=self.language)

        self.model = Kokoro(
            model_path=config.get("tts", "model_path", os.path.expanduser),
            voices_path=config.get("tts", "voices_path", os.path.expanduser)
        )

    def __synthesize(self, text: str, generation: int):
        if generation != self.generation:
            return

        try:
            if self.g2p is not None:
                phonemes, _ = self.g2p(text)
                samples, _ = self.model.create(
                    phonemes, voice=self.voice, speed=self.speed, is_phonemes=True)
            else:
                samples, _ = self.model.create(
                    text, voice=self.voice, speed=self.speed, lang=self.language)

            if generation != self.generation:
                return

            audio = np.asarray(samples, dtype=np.float32).reshape(-1)
            chunk_frames = 960 # 40ms

            for start in range(0, len(audio), chunk_frames):
                chunk = audio[start:start + chunk_frames]

                with self._output_lock:
                    if generation != self.generation:
                        return

                    self._output_stream.write(chunk.tobytes())
            
        except sd.PortAudioError:
            if generation != self.generation:
                return
            raise

        finally:
            self.last_used = time.monotonic()

    def __finish_speaking(self, generation: int):
        if generation == self.generation:
            self.is_speaking = False

    def unload_if_idle(self):
        idle_for = time.monotonic() - self.last_used
        
        if self.model is not None and idle_for >= self.unload_after:
            log.info("Unloading kokoro")
            self.model = None
            self.g2p = None
            gc.collect()

    def say(self, text: str, generation: Optional[int] = None):
        if generation is None:
            generation = self.generation

        if self.model is None:
            self.__init_model()

        self._speech_executor.submit(
            self.__synthesize, text, generation)

    def speak(self, text: str, generation: Optional[int] = None):
        sentences = []

        self.is_speaking = True
        self._speech_buffer += text

        if not generation:
            generation = self.generation

        while match := re.search(r"[.!?:]\s+|\n+", self._speech_buffer):
            sentence = self._speech_buffer[:match.end()].strip()
            self._speech_buffer = self._speech_buffer[match.end():]

            if sentence:
                sentences.append(sentence)

        for sentence in sentences:
            log.debug(f"_speech_executor.submit({generation}) -> {sentence}")
            self.say(sentence, generation)

    def done_speaking(self, generation: int):
        text = self._speech_buffer.strip()
        self._speech_buffer = ""

        if text:
            self._speech_executor.submit(self.__synthesize, text, generation)
            log.debug(f"done_speaking: _speech_executor.submit({generation}) -> {text}")

        self._speech_executor.submit(self.__finish_speaking, generation)

    def shut_up(self):
        if not self.is_speaking:
            return

        self.generation += 1
        self.is_speaking = False
        self._speech_buffer = ""

        with self._output_lock:
            pass

class WhisperWrapper:
    def __init__(self):
        self.model = None
        self.unload_after = config.get("stt", "unload_after", parse_duration)
        self.last_used = time.monotonic()

        if config.get("stt", "preload", bool):
            self.__init_model()

    def __init_model(self):
        log.info("Initializing whisper...")
        from faster_whisper import WhisperModel

        device = "auto"
        if config.get("stt", "prefer_cpu", bool):
            device = "cpu"

        compute_type = "int8" if device == "cpu" else "float16" 

        log.debug(f"WhisperWrapper: device -> {device}")
        log.debug(f"WhisperWrapper: compute type -> {compute_type}")

        self.model = WhisperModel(
            config.get("stt", "model"),
            device=device,
            compute_type=compute_type,
        )
    
    def unload_if_idle(self):
        idle_for = time.monotonic() - self.last_used

        if self.model is not None and idle_for >= self.unload_after:
            log.info("Unloading whisper")
            self.model.model.unload_model()
            self.model = None
            gc.collect()

    def transcribe(self, audio: np.ndarray):
        if self.model is None:
            self.__init_model()

        try:
            segments, info = self.model.transcribe(audio)
            out = "".join(segment.text for segment in segments).strip()
        finally:
            self.last_used = time.monotonic()

        return out

class Voice:
    def __init__(self):    
        self.filter = SpeechFilter()
        self.kokoro = KokoroWrapper()
        self.whisper = WhisperWrapper()

        self._listen_future: Optional[Future] = None
        self._stop_recording: Optional[Callable] = None

    def transcribe(self, audio: np.ndarray):
        return self.whisper.transcribe(audio)

    def get_generation(self):
        return self.kokoro.generation

    def say(self, text: str):
        """
        Unbuffered -> gets text -> says it
        """
        text = self.filter.apply(text)
        self.kokoro.say(text)

    def speak(self, text: str, generation: int):
        """
        Buffered: stores pieces and says as the whole sentence arrives
        needs done_speaking() when finished        
        """

        text = self.filter.apply(text)
        self.kokoro.speak(text, generation)

    def done_speaking(self, generation: int):
        """
        Flush any buffered text that doesn't end with punctuation.
        """
        self.kokoro.done_speaking(generation)

    def shut_up(self):
        self.kokoro.shut_up()

    def listen(self):
        """
        Start recording user audio.
        Call done_listening when done
        """

        if self.is_listening():
            raise RuntimeError("Already listening.")

        self._listen_future, self._stop_recording = record_audio()

    def done_listening(self) -> str:
        """
        Finish audio input recording,
        return transcribed text
        """

        if not self.is_listening():
            raise RuntimeError("Not currently listening.")

        self._stop_recording()

        try:
            audio = self._listen_future.result()
            return self.transcribe(audio)
        finally:
            self._listen_future = None
            self._stop_recording = None

    def is_listening(self):
        return self._listen_future is not None and self._stop_recording is not None
