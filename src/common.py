import sounddevice as sd

from datetime import datetime

def today():
    return datetime.today().strftime('%Y-%m-%d')

def record_audio(callback, sample_rate=16000):
    return sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        callback=callback,
    )