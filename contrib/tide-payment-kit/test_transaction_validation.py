"""Offline transaction output validation tests. No node or funds needed."""
import unittest
from decimal import Decimal
from payment_model import new_invoice, observe, Status
from transaction_validation import verify_transaction, TransactionValidationError

TXID = "a" * 64


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.invoice = new_invoice("invoice-1", "merchant-address", "1.25", 100, 200)

    def tx(self, outputs=None, confirmations=6):
        return {"txid": TXID, "confirmations": confirmations, "vout": outputs or [
            {"n": 0, "value": 1.25, "scriptPubKey": {"address": "merchant-address"}}
        ]}

    def test_valid_payment_can_update_model(self):
        verified = verify_transaction(self.invoice, self.tx())
        self.assertEqual(verified["received_tdc"], Decimal("1.25"))
        updated = observe(self.invoice, **verified, now=150)
        self.assertEqual(updated.status, Status.PAID)

    def test_multiple_outputs_same_address_sum(self):
        outputs = [
            {"n": 0, "value": "0.5", "scriptPubKey": {"address": "merchant-address"}},
            {"n": 1, "value": "0.75", "scriptPubKey": {"addresses": ["merchant-address"]}},
            {"n": 2, "value": 10, "scriptPubKey": {"address": "change-address"}},
        ]
        self.assertEqual(verify_transaction(self.invoice, self.tx(outputs))["received_tdc"], Decimal("1.25"))

    def test_wrong_address_rejected(self):
        outputs = [{"n": 0, "value": 100, "scriptPubKey": {"address": "someone-else"}}]
        with self.assertRaises(TransactionValidationError):
            verify_transaction(self.invoice, self.tx(outputs))

    def test_zero_value_rejected(self):
        outputs = [{"n": 0, "value": 0, "scriptPubKey": {"address": "merchant-address"}}]
        with self.assertRaises(TransactionValidationError):
            verify_transaction(self.invoice, self.tx(outputs))

    def test_duplicate_output_index_rejected(self):
        outputs = [
            {"n": 0, "value": 1, "scriptPubKey": {"address": "merchant-address"}},
            {"n": 0, "value": 1, "scriptPubKey": {"address": "merchant-address"}},
        ]
        with self.assertRaises(TransactionValidationError):
            verify_transaction(self.invoice, self.tx(outputs))

    def test_bad_precision_rejected(self):
        outputs = [{"n": 0, "value": "1.000000001", "scriptPubKey": {"address": "merchant-address"}}]
        with self.assertRaises(TransactionValidationError):
            verify_transaction(self.invoice, self.tx(outputs))

    def test_bad_confirmation_rejected(self):
        with self.assertRaises(TransactionValidationError):
            verify_transaction(self.invoice, self.tx(confirmations=-1))

    def test_ambiguous_address_rejected(self):
        outputs = [{"n": 0, "value": 2, "scriptPubKey": {"addresses": ["merchant-address", "other"]}}]
        with self.assertRaises(TransactionValidationError):
            verify_transaction(self.invoice, self.tx(outputs))


if __name__ == "__main__":
    unittest.main()
