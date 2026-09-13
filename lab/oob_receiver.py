"""OOB RECEIVER — the Smith's local blind-proof ear (Vague 3.1).

The interact.sh pattern, self-hosted in the lab: a tiny HTTP listener
that LOGS every hit with a unique nonce-path. An SSRF/blind candidate
fires at /hit/<nonce>; the receiver's log IS the receipt — the proof
that the target's server made an outbound call under our control.

Run:  python lab/oob_receiver.py   (port 19090)
Proof: the log line {'nonce': …} in oob_hits.log — the harness's oob
mode (and the doctrine) reads it as a CONFIRMED blind verdict.
"""
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 19090
LOG = __file__.rsplit("\\", 1)[0] + "\\oob_hits.log"


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        nonce = self.path.rsplit("/", 1)[-1] or "unknown"
        hit = {"ts": time.time(), "nonce": nonce,
               "from": self.client_address[0], "path": self.path}
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(hit) + "\n")
        b = b"receipt-ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"oob receiver on :{PORT} — hits logged to {LOG}")
    HTTPServer(("127.0.0.1", PORT), H).serve_forever()
