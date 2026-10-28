"""Offline HTTP integration tests for the loopback dashboard."""
import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("tide_dashboard", ROOT / "dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def test_index(self):
        with urlopen(self.url + "/", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"TIDE Node Monitor", response.read())
            self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_mocked_status(self):
        with patch.object(dashboard.monitor, "collect", return_value={"blocks": 42}):
            with urlopen(self.url + "/api/status", timeout=3) as response:
                body = json.load(response)
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["blocks"], 42)

    def test_rpc_failure_sanitized(self):
        with patch.object(dashboard.monitor, "collect", side_effect=RuntimeError("secret-password")):
            with self.assertRaises(HTTPError) as ctx:
                urlopen(self.url + "/api/status", timeout=3)
        self.assertEqual(ctx.exception.code, 503)
        self.assertNotIn("secret-password", ctx.exception.read().decode())

    def test_rejects_bad_host(self):
        request = Request(self.url + "/", headers={"Host": "evil.example"})
        with self.assertRaises(HTTPError) as ctx:
            urlopen(request, timeout=3)
        self.assertEqual(ctx.exception.code, 403)

    def test_rejects_cross_origin(self):
        request = Request(self.url + "/api/status", headers={"Origin": "https://evil.example"})
        with self.assertRaises(HTTPError) as ctx:
            urlopen(request, timeout=3)
        self.assertEqual(ctx.exception.code, 403)

    def test_unknown_route(self):
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.url + "/missing", timeout=3)
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
