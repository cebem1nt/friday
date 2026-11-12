from typing import Any, Generator, Optional
from src import log, config

from src.shared import (
    FRIDAY_SOCKET_PATH,  
    FRIDAY_LOCK_PATH, 
    friday_server_is_running
)

import os, json, socketserver, socket, time, threading

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

        self.fr.idle_actions()
        self._next_task = time.monotonic() + self.task_interval

class FridayServer(socketserver.StreamRequestHandler):
    server: FridayThreadingUnixStreamServer

    def __send_json(self, response: Any):
        self.wfile.write((json.dumps(response) + '\n').encode())
        self.wfile.flush()

    def __response(self, content: Optional[str]):
        if content is None:
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

    def __reload_friday(self):
        log.info("Importing Friday, ollama...")
        from src.friday.friday import Friday
        config.parse() # re-parse config
        self.server.fr = Friday()
        log.info("Friday was reloaded")

    def __match_request(self, req: dict):
        match req.get("function"):
            case "reload":         self.__response(self.__reload_friday())
            case "say":            self.__response(self.server.fr.say(req["text"]))
            case "set_model":      self.__response(self.server.fr.set_model(req["model"]))
            case "shut_up":        self.__response(self.server.fr.shut_up())
            case "wipe_context":   self.__response(self.server.fr.wipe_context())
            case "listen":         self.__response(self.server.fr.listen())
            case "done_listening": self.__response(self.server.fr.done_listening())
            case "get_messages":   self.__response(self.server.fr.get_messages(False, False))

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
                        req.get("audio"),
                        model=req.get("model"),
                        think=req.get("think"),
                        silent=req.get("silent"),
                        one_shot=req.get("one_shot"),
                        say_thinking_quote=req.get("say_thinking_quote")
                    ))
                else:
                    self.__response(self.server.fr.reply(
                        req["prompt"],
                        req.get("images"),
                        req.get("audio"),
                        model=req.get("model"),
                        think=req.get("think"),
                        silent=req.get("silent"),
                        one_shot=req.get("one_shot"),
                        say_thinking_quote=req.get("say_thinking_quote"),
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
            
            except BrokenPipeError:
                self.server.fr.unstage_turn()

            except KeyError as e:
                self.server.fr.unstage_turn()
                self.__response_error(f"Required argument is missing: {e.args[0]}")

            except Exception as exc:
                self.server.fr.unstage_turn()
                self.__response_error(f"internal error: {exc}")
                raise exc

def serve():
    if friday_server_is_running():
        log.fatal("Friday server is already running")

    with open(FRIDAY_LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))

    if os.path.exists(FRIDAY_SOCKET_PATH):
        os.unlink(FRIDAY_SOCKET_PATH)
        
    with FridayThreadingUnixStreamServer(FRIDAY_SOCKET_PATH, FridayServer) as server:
        os.chmod(FRIDAY_SOCKET_PATH, 0o600)        
        os.chdir(os.getenv("HOME"))

        log.info(f"Ready on {FRIDAY_SOCKET_PATH}")

        try:
            server.serve_forever()
        except (KeyboardInterrupt, EOFError):
            exit(0)
        finally:
            os.unlink(FRIDAY_SOCKET_PATH)