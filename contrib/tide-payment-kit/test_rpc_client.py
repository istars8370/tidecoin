"""Mock-only tests for local RPC payment inspection; no node required."""
import unittest
from unittest.mock import Mock, patch
from payment_model import new_invoice
from rpc_client import TideRPC, RPCError, inspect_payment

TX = "a" * 64
BLOCK = "b" * 64


class RPCClientTests(unittest.TestCase):
    def setUp(self):
        self.invoice = new_invoice("order", "merchant", "1.25", 100, 200)
        self.tx = {"txid": TX, "blockhash": BLOCK, "confirmations": 6,
                   "vout": [{"n": 0, "value": "1.25",
                             "scriptPubKey": {"address": "merchant"}}]}

    def mock_rpc(self, chain="main", confirmations=6):
        return Mock(
            blockchain_info=Mock(return_value={"chain": chain}),
            raw_transaction=Mock(return_value=self.tx),
            block_header=Mock(return_value={"hash": BLOCK, "confirmations": confirmations}),
        )

    def test_inspect_confirmed_payment(self):
        result = inspect_payment(self.mock_rpc(), self.invoice, TX, "main")
        self.assertEqual(str(result["received_tdc"]), "1.25")
        self.assertEqual(result["confirmations"], 6)
        self.assertEqual(result["blockhash"], BLOCK)

    def test_wrong_network(self):
        with self.assertRaises(RPCError):
            inspect_payment(self.mock_rpc(chain="test"), self.invoice, TX, "main")

    def test_orphaned_block(self):
        with self.assertRaises(RPCError):
            inspect_payment(self.mock_rpc(confirmations=-1), self.invoice, TX, "main")

    def test_confirmation_disagreement(self):
        with self.assertRaises(RPCError):
            inspect_payment(self.mock_rpc(confirmations=5), self.invoice, TX, "main")

    def test_unconfirmed_transaction(self):
        self.tx["confirmations"] = 0
        with self.assertRaises(RPCError):
            inspect_payment(self.mock_rpc(), self.invoice, TX, "main")

    def test_wrong_payment_address(self):
        self.tx["vout"][0]["scriptPubKey"]["address"] = "attacker"
        with self.assertRaises(ValueError):
            inspect_payment(self.mock_rpc(), self.invoice, TX, "main")

    def test_reject_remote_url(self):
        for url in ("http://example.com:8754", "http://127.0.0.1.evil.com:8754",
                    "http://user:pass@localhost:8754", "https://localhost:8754",
                    "http://localhost:8754/other"):
            with self.subTest(url=url), self.assertRaises(RPCError):
                TideRPC(url=url, user="u", password="p")

    def test_only_read_methods(self):
        rpc = TideRPC(url="http://127.0.0.1:8754", user="u", password="p")
        with self.assertRaises(RPCError):
            rpc._call("sendtoaddress", ["destination", 10])

    def test_txid_validation_before_network(self):
        rpc = TideRPC(url="http://127.0.0.1:8754", user="u", password="p")
        with self.assertRaises(RPCError):
            rpc.raw_transaction("not-a-txid")


if __name__ == "__main__":
    unittest.main()
