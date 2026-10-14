import os, json, socketserver
from typing import Any, Callable, Optional

from src import log

SOCKET_PATH = os.path.join(
    os.environ["XDG_RUNTIME_DIR"], "friday.sock")

class FridayServer(socketserver.StreamRequestHandler):
    def _send_json(self, response: Any):
        self.wfile.write((json.dumps(response) + "\n").encode())
        self.wfile.flush()

    def _send(self, reply: Optional[str]):
        if reply == None:
            reply = "ok"

        self._send_json({"reply": reply})
    
    def _stream(self, fn: Callable, **kwargs):
        for t, chunk in fn(**kwargs):
            self._send_json({
                "type": t,
                "chunk": chunk,
            })

        self._send_json({"type": "done"})

    def __match_request(self, r: dict):
        match r["function"]:
            case "converse":        self._stream(self.server.fr.converse)
            case "reply":           self._stream(self.server.fr.reply, prompt=r["prompt"])
            case "converse_text":   self._send(self.server.fr.converse(stream=False))
            case "reply_text":      self._send(self.server.fr.reply(r["prompt"], stream=False))
            case "shut_up":         self._send(self.server.fr.shut_up())
            case "say":             self._send(self.server.fr.say(r["text"]))
            case "listen":          self._send(self.server.fr.listen())
            case "done_listening":  self._send(self.server.fr.done_listening())

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
                self._send_json({"error": f"internal error: {exc}"})
                raise exc

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