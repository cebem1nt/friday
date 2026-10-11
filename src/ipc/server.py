import os, json, socketserver

from src.friday import Friday
from typing import Any

SOCKET_PATH = os.path.join(
    os.environ["XDG_RUNTIME_DIR"], "friday.sock")

class FridayServer(socketserver.StreamRequestHandler):
    def __match_request(self, request: dict):
        match request["function"]:
            case "ask":
                self.ask(request["prompt"])

            case _:
                return False

        return True

    def send_json(self, response: Any):
        self.wfile.write((json.dumps(response) + "\n").encode())
        self.wfile.flush()

    def ask(self, prompt: str):
        for msg_type, message_chunk in self.server.fr.ask(prompt):
            self.send_json({
                "type": msg_type,
                "chunk": message_chunk,
            })

        self.send_json({"type": "done"})

    def handle(self):
        for line in self.rfile:
            try:
                request = json.loads(line)

                if not self.__match_request(request):
                    self.send_json({"error": "unknown request function"})
                
            except Exception as exc:
                self.send_json({"type": "error", "error": str(exc)})

def friday_serve():
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    with socketserver.UnixStreamServer(SOCKET_PATH, FridayServer) as server:
        os.chmod(SOCKET_PATH, 0o600)
        server.fr = Friday()
        print(f"Ready on {SOCKET_PATH}", flush=True)
        server.serve_forever()