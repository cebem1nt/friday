import os, json, socketserver

from typing import Any

from src import log

SOCKET_PATH = os.path.join(
    os.environ["XDG_RUNTIME_DIR"], "friday.sock")

class FridayServer(socketserver.StreamRequestHandler):
    def _send_json(self, response: Any):
        self.wfile.write((json.dumps(response) + "\n").encode())
        self.wfile.flush()

    def _send_reply(self, reply: str):
        self._send_json({"reply": reply})
    
    def __reply(self, prompt: str):
        for msg_type, message_chunk in self.server.fr.reply(prompt):
            self._send_json({
                "type": msg_type,
                "chunk": message_chunk,
            })

        self._send_json({"type": "done"})

    def __listen_or_reply(self):
        for msg_type, message_chunk in self.server.fr.listen_or_reply():
            self._send_json({
                "type": msg_type,
                "chunk": message_chunk,
            })

        self._send_json({"type": "done"})

    def __match_request(self, request: dict):
        match request["function"]:
            case "reply":
                self.__reply(request["prompt"])

            case "listen":
                self.server.fr.listen()
                self._send_reply("ok")

            case "listen_or_reply":
                self.__listen_or_reply()

            case "done_listening":
                content = self.server.fr.done_listening()
                self._send_reply(content)

            case "shut_up":
                self.server.fr.shut_up()
                self._send_reply("ok")

            case "say":
                self.server.fr.say(request["text"])
                self._send_reply("ok")

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
                log.error(str(exc))
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