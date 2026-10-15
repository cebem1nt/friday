import socket, os, json
from typing import Any, BinaryIO
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

    def reply(self, prompt: str):
        with self._connection() as con:
            self._send_json({ 
                "function": "reply", 
                "prompt": prompt,
            }, con)

            while True:
                response = self._get_response(con)

                if response["type"] == "done":
                    return

                yield response["type"], response["chunk"]

    def converse(self):
        with self._connection() as con:
            self._send_json({"function": "converse"}, con)

            while True:
                response = self._get_response(con)

                if response["type"] == "done":
                    return

                yield response["type"], response["chunk"]

    def converse_text(self):
        with self._connection() as con:
            self._send_json({"function": "converse_text"}, con)
            return self._get_response(con)

    def reply_text(self, prompt: str):
        with self._connection() as con:
            self._send_json({"function": "reply_text", "prompt": prompt}, con)
            return self._get_response(con)

    def listen(self):
        with self._connection() as con:
            self._send_json({"function": "listen"}, con)
            return self._get_response(con)

    def done_listening(self):
        with self._connection() as con:
            self._send_json({"function": "done_listening"}, con)
            return self._get_response(con).get("reply")

    def shut_up(self):
        with self._connection() as con:
            self._send_json({"function": "shut_up"}, con)
            return self._get_response(con)

    def say(self, text: str):
        with self._connection() as con:
            self._send_json({
                "function": "say",
                "text": text
            }, con)
            
            return self._get_response(con) 
