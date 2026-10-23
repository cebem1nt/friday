from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Optional

from src.shared import parse_duration
from src import config, log

import numpy as np
import sounddevice as sd
import re, os, threading, time

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

class Voice:
    def __init__(self):    
        self._speech_buffer = ""
        self._buffer_lock = threading.Lock()
        self._speech_executor = ThreadPoolExecutor(max_workers=1)

        # Audio chunks are tagged with a generation number. stop_speaking()
        # changes the generation, making old queued chunks invalid.
        self.generation = 0

        self.kokoro = None
        self.whisper = None

        self.kokoro_unload_after = config.get("tts", "unload_after", parse_duration)
        self.whisper_unload_after = config.get("stt", "unload_after", parse_duration)

        self.voice = config.get("tts", "voice")
        self.speed = config.get("tts", "speed", float)

        if config.get("tts", "pre_allocate", bool):
            self.__init_kokoro()

        if config.get("stt", "pre_allocate", bool):
            self.__init_whisper()

        log.info("VoiceProvider: Setting up sd.RawOutputStream...")
        import sounddevice as sd
        self._output_stream = sd.RawOutputStream(
            samplerate=24000,
            channels=1,
            dtype="float32",
        )

        log.info("VoiceProvider: Starting sd.RawOutputStream...")
        self._output_stream.start()
        
        self._kokoro_last_used = time.monotonic()
        self._whisper_last_used = time.monotonic()
        self._stream_lock = threading.Lock()
        self._listen_lock = threading.Lock()
        self._listen_future: Optional[Future] = None
        self._stop_recording: Optional[Callable] = None

    def __init_whisper(self):
        log.info("VoiceProvider: Setting up whisper...")
        from faster_whisper import WhisperModel

        device = "auto"
        if config.get("stt", "prefer_cpu", bool):
            device = "cpu"

        compute_type = "int8" if device == "cpu" else "float16" 

        self.whisper = WhisperModel(
            config.get("stt", "model"),
            device=device,
            compute_type=compute_type,
        )

    def __init_kokoro(self):
        log.info("VoiceProvider: Setting up kokoro...")

        if config.get("tts", "prefer_cpu", bool):
            os.environ["ONNX_PROVIDER"] = "CPUExecutionProvider"

        from kokoro_onnx import Kokoro

        self.language = config.get("tts", "language")
        self.g2p = None

        if not self.language.startswith("en"):
            from misaki.espeak import EspeakG2P

            self.g2p = EspeakG2P(language=self.language)

        self.kokoro = Kokoro(
            model_path=config.get("tts", "model_path", os.path.expanduser),
            voices_path=config.get("tts", "voices_path", os.path.expanduser)
        )

    def __synthesize(self, text: str, generation: int):
        if generation != self.generation:
            return

        try:
            if self.g2p is not None:
                phonemes, _ = self.g2p(text)
                samples, _ = self.kokoro.create(
                    phonemes, voice=self.voice, speed=self.speed, is_phonemes=True)
            else:
                samples, _ = self.kokoro.create(
                    text, voice=self.voice, speed=self.speed, lang=self.language)

            if generation != self.generation:
                return

            with self._stream_lock:
                if generation != self.generation:
                    return

                self._output_stream.write(samples.tobytes())
                
        except sd.PortAudioError:
            if generation != self.generation:
                return
            raise

        finally:
            self._kokoro_last_used = time.monotonic()

    def unload_kokoro_if_idle(self):
        idle_for = time.monotonic() - self._kokoro_last_used
        
        if self.kokoro is not None and idle_for >= self.kokoro_unload_after:
            log.info("Unloading kokoro")
            self.kokoro = None
            self.g2p = None

    def unload_whisper_if_idle(self):
        idle_for = time.monotonic() - self._whisper_last_used

        if self.whisper is not None and idle_for >= self.whisper_unload_after:
            log.info("Unloading whisper")
            self.whisper.model.unload_model()
            self.whisper = None

    def say(self, text: str, generation: Optional[int] = None):
        """
        Unbuffered -> gets text -> says it
        """
        if generation is None:
            generation = self.generation

        if self.kokoro is None:
            self.__init_kokoro()

        self._speech_executor.submit(
            self.__synthesize, text, self.generation)

    def speak(self, text: str, generation: int):
        """
        Buffered -> stores pieces and says as the whole sentence arrives
        needs done_speaking() when finished        
        """
        
        sentences = []

        with self._buffer_lock:
            self._speech_buffer += text

            while match := re.search(r"[.!?:]\s+", self._speech_buffer):
                sentence = self._speech_buffer[:match.end()].strip()
                self._speech_buffer = self._speech_buffer[match.end():]

                if sentence:
                    sentences.append(sentence)

        for sentence in sentences:
            if self.generation != generation:
                return

            log.debug(f"_speech_executor.submit({generation}) -> {sentence}")
            self.say(sentence, generation)

    def done_speaking(self, generation: int):
        """
        Flush any buffered text that doesn't end with punctuation.
        """
        
        with self._buffer_lock:
            text = self._speech_buffer.strip()
            self._speech_buffer = ""

        if text:
            log.debug(f"done_speaking: _speech_executor.submit({generation}) -> {text}")
            self._speech_executor.submit(self.__synthesize, text, generation)

    def listen(self):
        with self._listen_lock:
            if self.is_listening():
                raise RuntimeError("Already listening.")

            self._listen_future, self._stop_recording = record_audio()

    def done_listening(self) -> str:
        with self._listen_lock:
            if not self.is_listening():
                raise RuntimeError("Not currently listening.")

            future = self._listen_future
            self._stop_recording()

            try:
                audio = future.result()
                return self.transcribe(audio)
            finally:
                self._listen_future = None
                self._stop_recording = None

    def shut_up(self):
        with self._buffer_lock:
            self.generation += 1
            log.debug(f"shifted self.generation = {self.generation}")
            self._speech_buffer = ""

        with self._stream_lock:
            pass
        
    def transcribe(self, audio: np.ndarray):
        if self.whisper is None:
            self.__init_whisper()

        try:
            segments, info = self.whisper.transcribe(audio)
            out = "".join(segment.text for segment in segments).strip()
        finally:
            self._whisper_last_used = time.monotonic()

        return out

    def is_listening(self):
        return self._listen_future is not None and self._stop_recording is not None
