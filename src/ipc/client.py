import socket, os, json

from typing import Any

SOCKET_PATH = os.path.join(
    os.environ["XDG_RUNTIME_DIR"], "friday.sock")

class FridayClient:
    def __init__(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(SOCKET_PATH)
        self.stream = self.sock.makefile("rwb")

    def send_json(self, response: Any):
        self.stream.write((json.dumps(response) + "\n").encode())
        self.stream.flush()

    def ask(self, prompt: str):
        request = {
            "function": "ask",
            "prompt": prompt
        }

        self.send_json(request)
        while True:
            line = self.stream.readline()
            response = json.loads(line)

            if response.get("error"):
                raise Exception(response["error"])

            if response["type"] == "done":
                return

            yield response["type"], response["chunk"]
        
    def transcribe(self, audio):
        pass

    def interrupt_speaking(self):
        pass

    def say(self, text: str):
        pass