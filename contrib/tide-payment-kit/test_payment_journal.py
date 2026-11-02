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

    def test_shared_address_rejected_for_other_invoice(self):
        other = new_invoice("order-2", "example-address", "2", 100, 200)
        with self.assertRaises(JournalError):
            self.journal.register(other)
        self.assertEqual(self.journal.history("order-2"), [])

    def test_distinct_address_registration_allowed(self):
        other = new_invoice("order-2", "different-address", "2", 100, 200)
        self.assertTrue(self.journal.register(other))

    def test_shared_address_rejected_after_reopen(self):
        self.journal.close()
        self.journal = PaymentJournal(self.path)
        other = new_invoice("order-2", "example-address", "2", 100, 200)
        with self.assertRaises(JournalError):
            self.journal.register(other)

    def test_integrity_report_clean(self):
        report = self.journal.diagnose_integrity()
        self.assertTrue(report["integrity_ok"])
        self.assertEqual(report["duplicate_addresses"], [])
        self.assertEqual(report["foreign_key_issue_count"], 0)

    def test_integrity_report_detects_legacy_duplicates(self):
        self.journal.db.execute(
            "INSERT INTO invoices VALUES (?,?,?,?,?)",
            ("legacy-2", "example-address", "2", 100, 200))
        self.journal.db.commit()
        report = self.journal.diagnose_integrity()
        self.assertEqual(report["duplicate_addresses"],
                         [{"address": "example-address", "invoice_count": 2}])

    def test_second_connection_rejects_shared_address(self):
        second = PaymentJournal(self.path)
        try:
            other = new_invoice("order-2", "example-address", "2", 100, 200)
            with self.assertRaises(JournalError):
                second.register(other)
        finally:
            second.close()

    def test_parallel_writers_cannot_claim_same_address(self):
        import threading
        barrier = threading.Barrier(2)
        outcomes = []
        failures = []
        lock = threading.Lock()

        def attempt(number):
            journal = PaymentJournal(self.path)
            invoice = new_invoice(
                "parallel-" + str(number), "parallel-shared-address",
                "2", 100, 200)
            try:
                barrier.wait(timeout=5)
                try:
                    journal.register(invoice)
                    result = "registered"
                except JournalError:
                    result = "rejected"
                with lock:
                    outcomes.append(result)
            except Exception as exc:
                with lock:
                    failures.append(repr(exc))
            finally:
                journal.close()

        workers = [threading.Thread(target=attempt, args=(i,)) for i in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=15)
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(failures, [], "Worker failures: " + repr(failures))
        self.assertCountEqual(outcomes, ["registered", "rejected"])
        count = self.journal.db.execute(
            "SELECT COUNT(*) FROM invoices WHERE address=?",
            ("parallel-shared-address",)).fetchone()[0]
        self.assertEqual(count, 1)

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
