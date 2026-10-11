import os, json, socketserver

SOCKET_PATH = os.path.join(
    os.environ["XDG_RUNTIME_DIR"], "friday.sock")

class FridayServer(socketserver.StreamRequestHandler):
    def handle(self):
        for line in self.rfile:
            request = json.loads(line)
            response = "aboba"

            self.wfile.write((json.dumps(response) + "\n").encode())
            self.wfile.flush()

def friday_serve():
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)

    with socketserver.UnixStreamServer(SOCKET_PATH, FridayServer) as server:
        os.chmod(SOCKET_PATH, 0o600)
        print(f"Ready on {SOCKET_PATH}", flush=True)
        server.serve_forever()