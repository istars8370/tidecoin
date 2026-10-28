#!/usr/bin/env python3
"""Local-only Tidecoin node status dashboard; no third-party packages."""
import json
import os
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import monitor

HOST = "127.0.0.1"
HTML = Path(__file__).with_name("dashboard.html")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path not in ("/", "/api/status"):
            self.send_error(404)
            return
        # Browsers may issue cross-origin requests to localhost. Require the
        # exact expected Host and Origin to reduce DNS-rebinding/CSRF exposure.
        expected = f"{HOST}:{self.server.server_port}"
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if host != expected or (origin and origin != f"http://{expected}"):
            self.send_error(403)
            return
        if path == "/":
            data = HTML.read_bytes()
            self._reply(200, "text/html; charset=utf-8", data)
            return
        try:
            result = monitor.collect()
            status = 200
            payload = {"ok": True, "data": result}
        except Exception:
            # No raw RPC errors, URLs, or credentials in HTTP responses.
            status = 503
            payload = {"ok": False, "error": "Local Tidecoin RPC unavailable"}
        self._reply(status, "application/json; charset=utf-8",
                    json.dumps(payload).encode("utf-8"))

    def _reply(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self' 'unsafe-inline'; "
                         "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
                         "base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Do not log browser query strings or sensitive local details.


def main():
    try:
        port = int(os.environ.get("TIDE_DASHBOARD_PORT", "8766"))
        if not 1024 <= port <= 65535:
            raise ValueError("Port must be between 1024 and 65535")
        server = ThreadingHTTPServer((HOST, port), Handler)
    except (OSError, ValueError) as exc:
        print(f"Cannot start dashboard: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"Open http://{HOST}:{port}/ in your browser. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
