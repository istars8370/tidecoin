"""Offline tests for payment observation journal; no real blockchain."""
import tempfile
import unittest
from pathlib import Path
from payment_model import new_invoice
from payment_journal import PaymentJournal, JournalError

TX = "a" * 64
BLOCK_A = "b" * 64
BLOCK_B = "c" * 64


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "journal.db"
        self.journal = PaymentJournal(self.path)
        self.invoice = new_invoice("order-1", "example-address", "1.25", 100, 200)
        self.journal.register(self.invoice)

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def test_registration_idempotent(self):
        self.assertFalse(self.journal.register(self.invoice))
        different = new_invoice("order-1", "different-address", "1.25", 100, 200)
        with self.assertRaises(JournalError):
            self.journal.register(different)

    def test_record_and_duplicate_idempotence(self):
        self.assertTrue(self.journal.record("order-1", TX, "1.25", 6, BLOCK_A,
                                            "candidate_paid", observed_at=120))
        self.assertFalse(self.journal.record("order-1", TX, "1.25", 6, BLOCK_A,
                                             "candidate_paid", observed_at=121))
        self.assertEqual(len(self.journal.history("order-1")), 1)

    def test_txid_cannot_be_claimed_by_other_invoice(self):
        self.journal.record("order-1", TX, "1.25", 1, BLOCK_A, "confirming")
        self.journal.register(new_invoice("order-2", "another-address", "2", 100, 200))
        with self.assertRaises(JournalError):
            self.journal.record("order-2", TX, "2", 6, BLOCK_A, "candidate_paid")
        self.assertEqual(self.journal.history("order-2"), [])

    def test_reorg_history_flags_review(self):
        self.journal.record("order-1", TX, "1.25", 6, BLOCK_A, "candidate_paid")
        self.journal.record("order-1", TX, "1.25", 0, None, "orphaned")
        self.journal.record("order-1", TX, "1.25", 1, BLOCK_B, "confirming")
        self.assertTrue(self.journal.needs_review("order-1"))
        self.assertEqual(len(self.journal.history("order-1")), 3)

    def test_history_persists_after_reopen(self):
        self.journal.record("order-1", TX, "1.25", 1, BLOCK_A, "confirming")
        self.journal.close()
        self.journal = PaymentJournal(self.path)
        self.assertEqual(len(self.journal.history("order-1")), 1)

    def test_invalid_input_rejected(self):
        with self.assertRaises(JournalError):
            self.journal.record("order-1", "bad", "1", 1, BLOCK_A, "confirming")
        with self.assertRaises(JournalError):
            self.journal.record("order-1", TX, "1", -1, BLOCK_A, "confirming")
        with self.assertRaises(JournalError):
            self.journal.record("order-1", TX, "1", 1, BLOCK_A, "paid")


if __name__ == "__main__":
    unittest.main()
