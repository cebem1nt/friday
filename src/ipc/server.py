import os, json, socketserver, sys, socket, time
from typing import Any, Generator, Optional

from src import log

SOCKET_PATH = os.path.join(
    os.environ["XDG_RUNTIME_DIR"], "friday.sock")

class FridayThreadingUnixStreamServer(socketserver.ThreadingUnixStreamServer):
    def __init__(self, *args, task_interval: int = 60, **kwargs):
        super().__init__(*args, **kwargs)
        log.info("Importing Friday, ollama...")

        from src.friday.friday import Friday
        self.fr = Friday()
        self.task_interval = task_interval
        self._next_task = time.monotonic() + task_interval

    def service_actions(self):
        if time.monotonic() < self._next_task:
            return

        self.fr.unload_kokoro_if_idle()
        self.fr.unload_whisper_if_idle()

        self._next_task = time.monotonic() + self.task_interval


class FridayServer(socketserver.StreamRequestHandler):
    server: FridayThreadingUnixStreamServer

    def __send_json(self, response: Any):
        self.wfile.write((json.dumps(response) + '\n').encode())
        self.wfile.flush()

    def __response(self, content: Optional[str]):
        if content == None:
            content = "ok"

        self.__send_json({"response": content})

    def __response_error(self, msg: str):
        self.__send_json({"error": msg})

    def __response_stream(self, gen: Generator[tuple[str, str]]):
        for t, chunk in gen:
            self.__send_json({
                "type": t,
                "chunk": chunk,
            })

        self.__send_json({"type": "done"})

    def __match_request(self, req: dict):
        match req.get("function"):
            case "say":            self.__response(self.server.fr.say(req["text"]))
            case "shut_up":        self.__response(self.server.fr.shut_up())
            case "wipe_context":   self.__response(self.server.fr.wipe_context())
            case "listen":         self.__response(self.server.fr.listen())
            case "done_listening": self.__response(self.server.fr.done_listening())
            case "get_messages":   self.__response(self.server.fr.get_messages(False))

            case "converse":
                if req.get("stream"):
                    self.__response_stream(self.server.fr.converse())
                else:
                    self.__response(self.server.fr.converse(stream=False))

            case "reply":
                if req.get("stream"):
                    self.__response_stream(self.server.fr.reply(
                        req["prompt"],
                        req.get("images"),
                        req.get("audio")
                    ))
                else:
                    self.__response(self.server.fr.reply(
                        req["prompt"],
                        req.get("images"),
                        req.get("audio"),
                        stream=False
                    ))

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
                    self.__response_error("unknown request function")
                
            except Exception as exc:
                self.__response_error(f"internal error: {exc}")
                raise exc

def friday_server_is_running():
    if not os.path.exists(SOCKET_PATH):
        return False

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        try:
            probe.connect(SOCKET_PATH)
            return True
        except:
            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)
            return False

def friday_serve():
    if friday_server_is_running():
        print("Friday server is allready running!", file=sys.stderr)
        exit(1)        

    with FridayThreadingUnixStreamServer(SOCKET_PATH, FridayServer) as server:
        os.chmod(SOCKET_PATH, 0o600)        
        os.chdir(os.getenv("HOME"))
        log.info(f"Ready on {SOCKET_PATH}")
        server.serve_forever()