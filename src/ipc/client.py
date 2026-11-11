import socket, os, json
from contextlib import contextmanager

from src.shared import FRIDAY_SOCKET_PATH, friday_server_is_running
from typing import Any, BinaryIO, Optional, Generator

class FridayClient:
    @contextmanager
    def connection(self):
        if not friday_server_is_running():
            raise RuntimeError("Friday server is not running")

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(FRIDAY_SOCKET_PATH)
            with s.makefile("rwb") as stream:
                yield stream

    def __send_json(self, content: Any, con: BinaryIO):
        con.write((json.dumps(content) + "\n").encode())
        con.flush()

    def __get_response(self, con: BinaryIO) -> dict:
        line = con.readline()
        response = json.loads(line)

        if err := response.get("error"):
            raise Exception(err)

        return response

    def __get_stream(
        self, 
        request: dict
    ) -> Generator[tuple[str, str]]:
        with self.connection() as con:
            self.__send_json(request, con)
            while True:
                response = self.__get_response(con)

                if response["type"] == "done":
                    return

                yield response["type"], response["chunk"]

    def reply(
        self,
        prompt: str,
        images: Optional[list[str]] = None, 
        audio: Optional[list[str]] = None,
        model: Optional[str] = None,
        think: Optional[bool] = None,
        stream: bool = True,
        silent: bool = False,
        one_shot: bool = False,
        say_thinking_quote: bool = True,
    ) -> Generator[tuple[str, str]] | str:
        if images:
            images = [os.path.realpath(img) for img in images]

        if audio:
            audio = [os.path.realpath(a) for a in audio]

        request = { 
            "function": "reply", 
            "prompt": prompt,
            "images": images,
            "audio": audio,
            "stream": stream,
            "say_thinking_quote": say_thinking_quote,
            "silent": silent,
            "model": model,
            "think": think,
            "one_shot": one_shot
        }

        if stream:
            return self.__get_stream(request)

        with self.connection() as con:
            self.__send_json(request, con)
            return self.__get_response(con).get("response")

    def converse(
        self, 
        stream: bool = True
    ) -> Generator[tuple[str, str]] | str:
        request = {
            "function": "converse",
            "stream": stream
        }

        if stream:
            return self.__get_stream(request)

        with self.connection() as con:
            self.__send_json(request, con)
            return self.__get_response(con).get("response")

    def shut_up(self):
        with self.connection() as con:
            self.__send_json({"function": "shut_up"}, con)
            return self.__get_response(con)

    def wipe_context(self):
        with self.connection() as con:
            self.__send_json({"function": "wipe_context" }, con)
            return self.__get_response(con)

    def say(self, text: str):
        with self.connection() as con:
            self.__send_json({
                "function": "say",
                "text": text
            }, con)
            
            return self.__get_response(con) 

    def set_model(self, model: str):
        with self.connection() as con:
            self.__send_json({
                "function": "set_model",
                "model": model
            }, con)
            
            return self.__get_response(con) 

    def listen(self):
        with self.connection() as con:
            self.__send_json({"function": "listen"}, con)
            return self.__get_response(con)

    def done_listening(self) -> str:
        with self.connection() as con:
            self.__send_json({"function": "done_listening"}, con)
            return self.__get_response(con).get("response")

    def get_messages(self) -> dict:
        with self.connection() as con:
            self.__send_json({"function": "get_messages"}, con)
            return self.__get_response(con).get("response") 

    def reload(self) -> dict:
        with self.connection() as con:
            self.__send_json({"function": "reload"}, con)
            return self.__get_response(con).get("response") 