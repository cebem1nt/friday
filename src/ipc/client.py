import socket, os, json

SOCKET_PATH = os.path.join(
    os.environ["XDG_RUNTIME_DIR"], "friday.sock")

class FridayClient:
    def __init__(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(SOCKET_PATH)
        self.stream = self.sock.makefile("rwb")

    def ask(self):
        self.stream.write((json.dumps({"path": "sixseven"}) + "\n").encode())
        self.stream.flush()
        response = self.stream.readline()
        print(response)