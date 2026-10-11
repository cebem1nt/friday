from piper import PiperVoice, SynthesisConfig
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import sounddevice as sd
import whisper, re

import config

class VoiceProvider:
    def __init__(self):
        self.voice = PiperVoice.load(config.voice_model)
        self.whisper = whisper.load_model(config.whisper_model)

        self._speech_executor = ThreadPoolExecutor(max_workers=1)
        self._speech_buffer = ""

        self._output_stream = sd.RawOutputStream(
            samplerate=self.voice.config.sample_rate,
            channels=1,
            dtype="int16",
        )

        self._output_stream.start()

    def transcribe(self, audio_chunks):
        audio = np.concatenate(audio_chunks).flatten()
        result = self.whisper.transcribe(audio, fp16=False)
        return result["text"].strip()

    def say(self, text: str):
        """
        Unbuffered -> gets text -> says it
        """

        for chunk in self.voice.synthesize(
            text,
            syn_config=SynthesisConfig(length_scale=0.7),
        ):
            self._output_stream.write(chunk.audio_int16_bytes)

    def speak(self, text: str):
        """
        Buffered -> stores pieces and says as the whole sentence arrives
        needs done_speaking() when finished
        """

        self._speech_buffer += text
        
        while match := re.search(r"[.!?](?:\s|$)", self._speech_buffer):
            sentence = self._speech_buffer[:match.end()].strip()
            self._speech_buffer = self._speech_buffer[match.end():]

            if sentence:
                self._speech_executor.submit(self.say, sentence)

    def done_speaking(self):
        text = self._speech_buffer.strip()
        self._speech_buffer = ""

        if text:
            self._speech_executor.submit(self.say, text)

    def close(self):
        self._speech_executor.shutdown(wait=True)
        self._output_stream.stop()
        self._output_stream.close()