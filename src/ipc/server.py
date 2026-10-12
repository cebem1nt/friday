import os, json, socketserver
import numpy as np

from src.friday import Friday
from typing import Any

from multiprocessing import shared_memory

SOCKET_PATH = os.path.join(
    os.environ["XDG_RUNTIME_DIR"], "friday.sock")

class FridayServer(socketserver.StreamRequestHandler):
    def __match_request(self, request: dict):
        match request["function"]:
            case "ask":
                self.ask(request["prompt"])

            case "transcribe":
                self.transcribe(request["meta"])    

            case "interrupt_speaking":
                self.server.fr.interrupt_speaking()
                self._reply("ok")

            case "say":
                self.server.fr.say(request["text"])
                self._reply("ok")

            case _:
                return False

        return True

    def _send_json(self, response: Any):
        self.wfile.write((json.dumps(response) + "\n").encode())
        self.wfile.flush()

    def _reply(self, reply: str):
        self.wfile.write((json.dumps({"reply": reply}) + "\n").encode())
        self.wfile.flush()

    def ask(self, prompt: str):
        for msg_type, message_chunk in self.server.fr.ask(prompt):
            self._send_json({
                "type": msg_type,
                "chunk": message_chunk,
            })

        self._send_json({"type": "done"})

    def transcribe(self, meta: dict):
        shm = shared_memory.SharedMemory(name=meta["name"])

        try: 
            audio = np.ndarray(
                meta["shape"],
                dtype=np.dtype(meta["dtype"]),
                buffer=shm.buf,
            )

            text = self.server.fr.transcribe(audio)
            self._reply(text)
        finally:
            shm.close()

    def handle(self):
        for line in self.rfile:
            try:
                request = json.loads(line)

                if not self.__match_request(request):
                    self._send_json({"error": "unknown request function"})
                
            except Exception as exc:
                self._send_json({"error": str(exc)})

def friday_serve():
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    with socketserver.ThreadingUnixStreamServer(SOCKET_PATH, FridayServer) as server:
        os.chmod(SOCKET_PATH, 0o600)
        server.fr = Friday()
        print(f"Ready on {SOCKET_PATH}", flush=True)
        server.serve_forever()