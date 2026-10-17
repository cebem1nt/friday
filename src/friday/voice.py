from concurrent.futures import ThreadPoolExecutor, Future

import numpy as np
import sounddevice as sd
import re, os, threading

from src import config, log
from typing import Callable

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
        self._generation = 0
        self.kokoro = None
        self.whisper = None

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
        
        self._stream_lock = threading.Lock()
        self._listen_lock = threading.Lock()
        self._listen_future: Future | None = None
        self._stop_recording: Callable | None = None

    def __init_whisper(self):
        log.info("VoiceProvider: Setting up whisper...")
        from faster_whisper import WhisperModel

        whisper_device = config.get("stt", "device")
        compute_type = "float16" if whisper_device == "cuda" else "int8"

        self.whisper = WhisperModel(
            config.get("stt", "model"),
            device=whisper_device,
            compute_type=compute_type,
        )

    def __init_kokoro(self):
        log.info("VoiceProvider: Setting up kokoro...")
        from kokoro_onnx import Kokoro

        self.kokoro = Kokoro(
            model_path=config.get("tts", "model_path", os.path.expanduser),
            voices_path=config.get("tts", "voices_path", os.path.expanduser)
        )

        self.voice = config.get("tts", "voice")

    def _synthesize(self, text: str, generation: int):
        if generation != self._generation:
            return

        samples, _ = self.kokoro.create(
            text,
            voice=self.voice,
            speed=1.0,
            lang="en-us",
        )

        if generation != self._generation:
            return

        try:
            with self._stream_lock:
                if generation != self._generation:
                    return

                self._output_stream.write(samples.tobytes())
                
        except sd.PortAudioError:
            if generation != self._generation:
                return
                
            raise

    def say(self, text: str):
        """
        Unbuffered -> gets text -> says it
        """
        if self.kokoro is None:
            self.__init_kokoro()

        self._speech_executor.submit(
            self._synthesize, text, self._generation)

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
            if self._generation != generation:
                return

            log.debug(f"_speech_executor.submit({generation}) -> {sentence}")

            if self.kokoro is None:
                self.__init_kokoro()

            self._speech_executor.submit(
                self._synthesize, sentence, generation
            )

    def done_speaking(self):
        """
        Flush any buffered text that doesn't end with punctuation.
        """
        
        with self._buffer_lock:
            text = self._speech_buffer.strip()
            self._speech_buffer = ""

        if text:
            self._speech_executor.submit(self._synthesize, text, self._generation)

    def listen(self):
        with self._listen_lock:
            if self.is_listening():
                raise RuntimeError("Already recording.")

            self._listen_future, self._stop_recording = record_audio()

    def done_listening(self) -> str:
        with self._listen_lock:
            if not self.is_listening():
                raise RuntimeError("Not currently recording.")

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
            self._generation += 1
            log.debug(f"shifted self._generation = {self._generation}")
            self._speech_buffer = ""

        with self._stream_lock:
            pass
        
    def transcribe(self, audio: np.ndarray):
        if self.whisper is None:
            self.__init_whisper()

        segments, info = self.whisper.transcribe(audio)
        return "".join(segment.text for segment in segments).strip()

    def is_listening(self):
        return self._listen_future is not None and self._stop_recording is not None
