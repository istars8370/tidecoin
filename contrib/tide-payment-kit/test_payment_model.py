"""Offline payment model tests; no real TDC, wallet or RPC required."""
import unittest
from decimal import Decimal
from payment_model import Status, amount, new_invoice, observe

TX = "a" * 64
OTHER = "b" * 64


class PaymentTests(unittest.TestCase):
    def setUp(self):
        self.invoice = new_invoice("order-001", "EXAMPLE_ADDRESS_NOT_VALIDATED", "12.5", 100, 200)

    def test_amount_validation(self):
        for bad in ("0", "-1", "NaN", "Infinity", "0.000000001", "invalid"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                amount(bad)
        self.assertEqual(amount("0.00000001"), Decimal("0.00000001"))

    def test_invoice_validation(self):
        with self.assertRaises(ValueError):
            new_invoice("x", "address", "1", 100, 100)

    def test_confirmation_flow(self):
        confirming = observe(self.invoice, TX, "12.5", 0, 110)
        self.assertEqual(confirming.status, Status.CONFIRMING)
        confirmed = observe(confirming, TX, "12.5", 6, 120)
        self.assertEqual(confirmed.status, Status.PAID)
        self.assertEqual(observe(confirmed, TX, "12.5", 7, 130), confirmed)

    def test_underpayment(self):
        state = observe(self.invoice, TX, "10", 8, 110)
        self.assertEqual(state.status, Status.UNDERPAID)

    def test_expiry(self):
        state = observe(self.invoice, TX, "12.5", 0, 200)
        self.assertEqual(state.status, Status.EXPIRED)

    def test_second_transaction_requires_review(self):
        first = observe(self.invoice, TX, "12.5", 1, 110)
        self.assertEqual(observe(first, OTHER, "12.5", 2, 120).status, Status.REVIEW)

    def test_invalid_transaction(self):
        with self.assertRaises(ValueError):
            observe(self.invoice, "not-a-txid", "12.5", 1, 110)


if __name__ == "__main__":
    unittest.main()
