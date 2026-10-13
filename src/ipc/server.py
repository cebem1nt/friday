import os, json, socketserver
import numpy as np

from typing import Any
from multiprocessing import shared_memory

from src import log

SOCKET_PATH = os.path.join(
    os.environ["XDG_RUNTIME_DIR"], "friday.sock")

class FridayServer(socketserver.StreamRequestHandler):
    def _send_json(self, response: Any):
        self.wfile.write((json.dumps(response) + "\n").encode())
        self.wfile.flush()

    def _reply(self, reply: str):
        self.wfile.write((json.dumps({"reply": reply}) + "\n").encode())
        self.wfile.flush()

    def __ask(self, prompt: str):
        for msg_type, message_chunk in self.server.fr.ask(prompt):
            self._send_json({
                "type": msg_type,
                "chunk": message_chunk,
            })

        self._send_json({"type": "done"})

    def __transcribe(self, meta: dict):
        shm = shared_memory.SharedMemory(name=meta["name"], create=False, track=False)

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

    def __match_request(self, request: dict):
        match request["function"]:
            case "ask":
                self.__ask(request["prompt"])

            case "transcribe":
                self.__transcribe(request["meta"])    

            case "shut_up":
                self.server.fr.shut_up()
                self._reply("ok")

            case "say":
                self.server.fr.say(request["text"])
                self._reply("ok")

            case _:
                return False

        return True

    def handle(self):
        for line in self.rfile:
            try:
                request = json.loads(line)
                log.info(f"Got request: {request}")

                if not self.__match_request(request):
                    log.warn(f"Unknown function: {request.get('function')}")
                    self._send_json({"error": "unknown request function"})
                
            except Exception as exc:
                log.error(str(exc.with_traceback))
                self._send_json({"error": str(exc)})

def friday_serve():
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    with socketserver.ThreadingUnixStreamServer(SOCKET_PATH, FridayServer) as server:
        os.chmod(SOCKET_PATH, 0o600)
        log.info("Importing Friday, ollama...")
        from src.friday.friday import Friday
        server.fr = Friday()
        log.ok(f"Ready on {SOCKET_PATH}")
        server.serve_forever()