import socket, os, json
from contextlib import contextmanager

from typing import Any, BinaryIO, Optional, Generator

SOCKET_PATH = os.path.join(
    os.environ["XDG_RUNTIME_DIR"], "friday.sock")

class FridayClient:
    @contextmanager
    def connection(self):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(SOCKET_PATH)
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

    def __get_stream(self, con: BinaryIO):
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
        stream: bool = True
    ) -> Generator[tuple[str, str]] | str:
        if images:
            images = [os.path.realpath(img) for img in images]

        if audio:
            audio = [os.path.realpath(a) for a in audio]

        with self.connection() as con:
            self.__send_json({ 
                "function": "reply", 
                "prompt": prompt,
                "images": images,
                "audio": audio,
                "stream": stream
            }, con)

            if stream:
                return self.__get_stream(con)
            
            return self.__get_response(con).get("response")

    def converse(
        self, 
        stream: bool = True
    ) -> Generator[tuple[str, str]] | str:
        with self.connection() as con:
            self.__send_json({
                "function": "converse",
                "stream": stream
            }, con)

            if stream:
                return self.__get_stream(con)
            
            return self.__get_response(con).get("response")

    def shut_up(self):
        with self.connection() as con:
            self.__send_json({"function": "shut_up"}, con)
            self.__get_response(con)

    def wipe_context(self):
        with self.connection() as con:
            self.__send_json({"function": "wipe_context" }, con)
            self.__get_response(con)

    def say(self, text: str):
        with self.connection() as con:
            self.__send_json({
                "function": "say",
                "text": text
            }, con)
            
            self.__get_response(con) 

    def listen(self):
        with self._connection() as con:
            self._send_json({"function": "listen"}, con)
            self.__get_response(con)

    def done_listening(self) -> str:
        with self._connection() as con:
            self._send_json({"function": "done_listening"}, con)
            return self.__get_response(con).get("response")