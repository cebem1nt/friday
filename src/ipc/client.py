import socket, os, json
import numpy as np

from typing import Any, BinaryIO
from multiprocessing import shared_memory
from contextlib import contextmanager

SOCKET_PATH = os.path.join(
    os.environ["XDG_RUNTIME_DIR"], "friday.sock")

class FridayClient:
    @contextmanager
    def _connection(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(SOCKET_PATH)
            with s.makefile("rwb") as stream:
                yield stream

    def _send_json(self, content: Any, stream: BinaryIO):
        stream.write((json.dumps(content) + "\n").encode())
        stream.flush()

    def _get_response(self, stream: BinaryIO) -> dict:
        line = stream.readline()
        response = json.loads(line)

        if err := response.get("error"):
            raise Exception(err)

        return response

    def ask(self, prompt: str):
        with self._connection() as stream:
            self._send_json({ 
                "function": "ask", 
                "prompt": prompt,
            }, stream)

            while True:
                response = self._get_response(stream)

                if response["type"] == "done":
                    return

                yield response["type"], response["chunk"]

    def transcribe(self, audio) -> str:
        shm = shared_memory.SharedMemory(create=True, size=audio.nbytes)
        shared_audio = np.ndarray(audio.shape, dtype=audio.dtype, buffer=shm.buf)
        shared_audio[:] = audio

        with self._connection() as stream:
            self._send_json({
                "function": "transcribe",
                "meta": {
                    "name": shm.name,
                    "shape": audio.shape,
                    "dtype": audio.dtype.str,
                },
            }, stream)

            try:
                reply = self._get_response(stream).get("reply")
            finally:
                shm.close()
                shm.unlink()

            return reply

    def shut_up(self):
        with self._connection() as stream:
            self._send_json({"function": "shut_up"}, stream)
            self._get_response(stream)

    def say(self, text: str):
        with self._connection() as stream:
            self._send_json({
                "function": "say",
                "text": text
            }, stream)
            
            self._get_response(stream) 
