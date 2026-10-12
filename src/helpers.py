import random, threading
import numpy as np

from typing import Callable
from datetime import datetime
from concurrent.futures import Future
from sounddevice import InputStream

def today():
    return datetime.today().strftime('%Y-%m-%d')
    
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
            with InputStream(
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

def random_thinking_quote():
    return random.choice([
        "Let me think",
        "Let me think about it",
        "I should think about it",
        "I'm thinking",
        "Okay, let me think for a moment",
        "Thinking",
        "I have to think about it",
        "Wait please, I gotta think"
    ])