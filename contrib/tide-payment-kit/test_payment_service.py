"""Offline mocked integration tests for payment_service."""
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from payment_model import new_invoice
from payment_journal import PaymentJournal, JournalError
from payment_service import assess_payment, record_orphan, PaymentServiceError
from rpc_client import RPCError

TX = "a" * 64
TX2 = "b" * 64
BLOCK = "c" * 64
BLOCK2 = "d" * 64


class FakeRPC:
    pass


class PaymentServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.journal = PaymentJournal(Path(self.temp.name) / "journal.db")
        self.invoice = new_invoice("order-1", "tide-address", "10", 100, 1000)

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def assess(self, received="10", confirmations=6, txid=TX, blockhash=BLOCK,
               now=200, invoice=None):
        observation = {"txid": txid, "received_tdc": Decimal(received),
                       "confirmations": confirmations, "blockhash": blockhash}
        with patch("payment_service.inspect_payment", return_value=observation):
            return assess_payment(self.journal, FakeRPC(), invoice or self.invoice,
                                  txid, "main", observed_at=now)

    def test_candidate_never_settles(self):
        result = self.assess()
        self.assertEqual(result["state"], "candidate_paid")
        self.assertFalse(result["settlement_authorized"])
        self.assertEqual(len(self.journal.history("order-1")), 1)

    def test_underpayment_review(self):
        self.assertEqual(self.assess(received="9")["state"], "review_required")

    def test_confirmation_threshold(self):
        self.assertEqual(self.assess(confirmations=5)["state"], "confirming")
        self.assertEqual(self.assess(confirmations=6)["state"], "candidate_paid")

    def test_expired_invoice_review(self):
        self.assertEqual(self.assess(now=1000)["state"], "review_required")

    def test_idempotent_observation(self):
        self.assess()
        self.assess()
        self.assertEqual(len(self.journal.history("order-1")), 1)

    def test_block_change_review(self):
        self.assess()
        result = self.assess(blockhash=BLOCK2)
        self.assertEqual(result["state"], "review_required")
        self.assertTrue(result["needs_review"])

    def test_other_tx_requires_review(self):
        self.assess()
        self.assertEqual(self.assess(txid=TX2)["state"], "review_required")

    def test_orphan_requires_prior_block(self):
        with self.assertRaises(PaymentServiceError):
            record_orphan(self.journal, "order-1", TX, "10")

    def test_orphan_blocks_future_candidate(self):
        self.assess()
        record_orphan(self.journal, "order-1", TX, "10", observed_at=201)
        self.assertEqual(self.assess(now=202)["state"], "review_required")

    def test_duplicate_tx_across_invoices(self):
        self.assess()
        second = new_invoice("order-2", "another-address", "10", 100, 1000)
        with self.assertRaises(JournalError):
            self.assess(invoice=second)

    def test_rpc_failure_does_not_create_observation(self):
        with patch("payment_service.inspect_payment", side_effect=RPCError("offline")):
            with self.assertRaises(RPCError):
                assess_payment(self.journal, FakeRPC(), self.invoice, TX, "main",
                               observed_at=200)
        self.assertEqual(self.journal.history("order-1"), [])

    def test_invalid_confirmation_threshold(self):
        with self.assertRaises(PaymentServiceError):
            assess_payment(self.journal, FakeRPC(), self.invoice, TX, "main",
                           required_confirmations=True)


if __name__ == "__main__":
    unittest.main()
