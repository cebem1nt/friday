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
        with self._connection() as stream:
            self._send_json({ 
                "function": "reply", 
                "prompt": prompt,
            }, stream)

            while True:
                response = self._get_response(stream)

                if response["type"] == "done":
                    return

                yield response["type"], response["chunk"]

    def listen_or_reply(self):
        with self._connection() as stream:
            self._send_json({
                "function": "listen_or_reply"
            }, stream)

            while True:
                response = self._get_response(stream)

                if response["type"] == "done":
                    return

                yield response["type"], response["chunk"]

    def listen(self):
        with self._connection() as stream:
            self._send_json({"function": "listen"}, stream)
            return self._get_response(stream)

    def done_listening(self):
        with self._connection() as stream:
            self._send_json({"function": "done_listening"}, stream)
            return self._get_response(stream).get("reply")

    def shut_up(self):
        with self._connection() as stream:
            self._send_json({"function": "shut_up"}, stream)
            return self._get_response(stream)

    def say(self, text: str):
        with self._connection() as stream:
            self._send_json({
                "function": "say",
                "text": text
            }, stream)
            
            return self._get_response(stream) 
