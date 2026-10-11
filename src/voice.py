from piper import PiperVoice, SynthesisConfig
from concurrent.futures import ThreadPoolExecutor, Future

import numpy as np
import sounddevice as sd
import re, whisper

import config, os, queue, threading

class VoiceProvider:
    def __init__(self):
        self.piper = PiperVoice.load(config.get("tts", "model_path", os.path.expanduser))
        self.whisper = whisper.load_model(config.get("stt", "model"))

        self.syn_config = SynthesisConfig(
            length_scale=config.get("tts", "voice_scale", float)
        )

        self._speech_buffer = ""
        self._buffer_lock = threading.Lock()
        self._speech_executor = ThreadPoolExecutor(max_workers=1)

        # Audio chunks are tagged with a generation number. stop_speaking()
        # changes the generation, making old queued chunks invalid.
        self._generation = 0

        self._stream_lock = threading.Lock()
        self._output_stream = sd.RawOutputStream(
            samplerate=self.piper.config.sample_rate,
            channels=1,
            dtype="int16",
        )
        self._output_stream.start()

    def _synthesize(self, text: str, generation: int):
        for chunk in self.piper.synthesize(text, syn_config=self.syn_config):
            if generation != self._generation:
                return

            try:
                with self._stream_lock:
                    if generation != self._generation:
                        return

                    self._output_stream.write(chunk.audio_int16_bytes)

            except sd.PortAudioError:
                # An abort during write is expected when interrupting.
                if generation != self._generation:
                    return
                raise

    def say(self, text: str) -> Future:
        """
        Unbuffered -> gets text -> says it
        """

        return self._speech_executor.submit(
            self._synthesize, text, self._generation)

    def speak(self, text: str):
        """
        Buffered -> stores pieces and says as the whole sentence arrives
        needs done_speaking() when finished        
        """
        
        sentences = []

        with self._buffer_lock:
            self._speech_buffer += text

            while match := re.search(r"[.!?](?:\s|$)", self._speech_buffer):
                sentence = self._speech_buffer[:match.end()].strip()
                self._speech_buffer = self._speech_buffer[match.end():]

                if sentence:
                    sentences.append(sentence)

        generation = self._generation

        for sentence in sentences:
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

    def interrupt_speaking(self):        
        with self._buffer_lock:
            self._generation += 1
            self._speech_buffer = ""

        with self._stream_lock:
            pass
        
    def transcribe(self, audio_chunks):
        audio = np.concatenate(audio_chunks).flatten()
        result = self.whisper.transcribe(audio, fp16=False)
        return result["text"].strip()