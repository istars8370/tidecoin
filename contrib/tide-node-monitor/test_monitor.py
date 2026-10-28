"""Offline tests for the Tidecoin node monitor. No running node required."""
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("monitor.py")
spec = importlib.util.spec_from_file_location("tide_monitor", SCRIPT)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class MonitorTests(unittest.TestCase):
    def test_valid_local_rpc_urls(self):
        for url in ("http://127.0.0.1:8754", "http://localhost:1234/", "http://[::1]:1234"):
            with self.subTest(url=url), patch.dict(os.environ, {"TIDE_RPC_URL": url}):
                self.assertEqual(monitor.local_rpc_url(), url)

    def test_rejects_unsafe_urls(self):
        urls = (
            "https://127.0.0.1:8754", "http://example.com:8754",
            "http://127.0.0.1.evil.com:8754", "http://localhost:8754@evil.com:80",
            "http://user:secret@localhost:8754", "http://localhost:8754/extra",
            "http://localhost:8754?secret=1", "http://localhost",
        )
        for url in urls:
            with self.subTest(url=url), patch.dict(os.environ, {"TIDE_RPC_URL": url}):
                with self.assertRaises(ValueError):
                    monitor.local_rpc_url()

    def test_rejects_unapproved_method_before_network(self):
        with self.assertRaises(ValueError):
            monitor.rpc("sendtoaddress")

    def test_missing_credentials(self):
        env = {"TIDE_RPC_URL": "http://127.0.0.1:8754"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError):
                monitor.rpc("getblockchaininfo")

    def test_collect_maps_expected_fields(self):
        replies = [
            {"chain": "main", "blocks": 100, "headers": 101,
             "verificationprogress": 0.9, "initialblockdownload": True},
            {"connections": 8},
            {"networkhashps": 1234, "difficulty": 2.5},
        ]
        with patch.object(monitor, "rpc", side_effect=replies) as mocked:
            result = monitor.collect()
        self.assertEqual(result["blocks"], 100)
        self.assertEqual(result["connections"], 8)
        self.assertEqual(result["network_hashps"], 1234)
        self.assertEqual([call.args[0] for call in mocked.call_args_list], list(monitor.METHODS))

    def test_rpc_response_and_authorization(self):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def read(self, *_):
                return json.dumps({"result": {"blocks": 123}, "error": None}).encode()

        class FakeOpener:
            def open(self, request, timeout):
                self.request = request
                self.timeout = timeout
                return FakeResponse()

        opener = FakeOpener()
        env = {"TIDE_RPC_URL": "http://localhost:8754",
               "TIDE_RPC_USER": "test", "TIDE_RPC_PASSWORD": "example"}
        with patch.dict(os.environ, env, clear=True), patch.object(
            monitor.urllib.request, "build_opener", return_value=opener
        ):
            result = monitor.rpc("getblockchaininfo")
        self.assertEqual(result["blocks"], 123)
        self.assertEqual(opener.timeout, 8)
        self.assertEqual(opener.request.get_method(), "POST")
        self.assertIn("Authorization", opener.request.headers)

    def test_rpc_error_rejected(self):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def read(self, *_):
                return b'{"result":null,"error":{"code":-1}}'
        class FakeOpener:
            def open(self, *_args, **_kwargs):
                return FakeResponse()
        with patch.dict(os.environ, {"TIDE_RPC_USER": "a", "TIDE_RPC_PASSWORD": "b"}), patch.object(
            monitor.urllib.request, "build_opener", return_value=FakeOpener()
        ):
            with self.assertRaises(RuntimeError):
                monitor.rpc("getblockchaininfo")


if __name__ == "__main__":
    unittest.main()
