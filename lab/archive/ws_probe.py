"""Raw WS handshake probe for /ws/mission — verifies the vite proxy path heals."""
import socket, base64, os, sys

req = (
    "GET /ws/mission HTTP/1.1\r\n"
    "Host: 127.0.0.1:8000\r\n"
    "Upgrade: websocket\r\n"
    "Connection: Upgrade\r\n"
    f"Sec-WebSocket-Key: {base64.b64encode(os.urandom(16)).decode()}\r\n"
    "Sec-WebSocket-Version: 13\r\n\r\n"
)
s = socket.create_connection(("127.0.0.1", 8000), timeout=6)
s.sendall(req.encode())
resp = s.recv(512).decode(errors="replace")
code = resp.split(" ")[1] if " " in resp else "?"
print("handshake:", "OK (101)" if code == "101" else f"ÉCHEC ({code})")
print(resp.splitlines()[0])
s.close()
