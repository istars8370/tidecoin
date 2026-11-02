"""Offline security tests for bounded RPC envelopes and type validation."""
import io
import json
import unittest
from unittest.mock import patch

from rpc_client import MAX_RPC_RESPONSE_BYTES, RPCError, TideRPC


class Response:
    status = 200

    def __init__(self, data, headers=None):
        self.body = io.BytesIO(data)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.body.read(size)


class RPCSecurityTests(unittest.TestCase):
    def setUp(self):
        self.rpc = TideRPC(url="http://127.0.0.1:12345", user="secret-user",
                           password="secret-password")

    def reply(self, payload, headers=None):
        data = json.dumps(payload).encode()
        with patch.object(self.rpc._opener, "open", return_value=Response(data, headers)):
            return self.rpc.blockchain_info()

    def test_valid_envelope(self):
        result = self.reply({"id": "payment-kit", "error": None,
                             "result": {"chain": "main"}})
        self.assertEqual(result["chain"], "main")

    def test_wrong_id_rejected(self):
        with self.assertRaises(RPCError):
            self.reply({"id": "other", "error": None, "result": {"chain": "main"}})

    def test_missing_result_rejected(self):
        with self.assertRaises(RPCError):
            self.reply({"id": "payment-kit", "error": None})

    def test_invalid_json_rejected_without_secrets(self):
        with patch.object(self.rpc._opener, "open", return_value=Response(b"{")):
            with self.assertRaises(RPCError) as ctx:
                self.rpc.blockchain_info()
        self.assertNotIn("secret-password", str(ctx.exception))

    def test_oversized_declared_length_rejected(self):
        with self.assertRaises(RPCError):
            self.reply({"id": "payment-kit", "error": None,
                        "result": {"chain": "main"}},
                       {"Content-Length": str(MAX_RPC_RESPONSE_BYTES + 1)})

    def test_oversized_stream_rejected(self):
        data = b" " * (MAX_RPC_RESPONSE_BYTES + 1)
        with patch.object(self.rpc._opener, "open", return_value=Response(data)):
            with self.assertRaises(RPCError):
                self.rpc.blockchain_info()

    def test_invalid_txid_type(self):
        with self.assertRaises(RPCError):
            self.rpc.raw_transaction(42)

    def test_invalid_block_hash_type(self):
        with self.assertRaises(RPCError):
            self.rpc.block_header(None)

    def test_no_implicit_rpc_endpoint(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RPCError):
                TideRPC(user="u", password="p")

    def test_no_rpc_error_message_leak(self):
        with patch.object(self.rpc._opener, "open",
                          side_effect=RuntimeError("secret-password")):
            with self.assertRaises(RPCError) as ctx:
                self.rpc.blockchain_info()
        self.assertNotIn("secret-password", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
