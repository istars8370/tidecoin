"""Validate a decoded transaction against an invoice (offline, no RPC calls).

This is a parser for externally supplied getrawtransaction(verbose=true)-style
data, NOT proof that a transaction is canonical, confirmed, or from a trusted node.
"""
from decimal import Decimal, InvalidOperation
import re

TXID = re.compile(r"^[0-9a-fA-F]{64}$")


class TransactionValidationError(ValueError):
    pass


def _satoshis(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise TransactionValidationError("Invalid output value type")
    try:
        d = Decimal(str(value))
    except InvalidOperation as exc:
        raise TransactionValidationError("Invalid output value") from exc
    if not d.is_finite() or d < 0 or d.as_tuple().exponent < -8:
        raise TransactionValidationError("Output value must be nonnegative with <=8 decimals")
    return int(d * 100_000_000)


def verify_transaction(invoice, tx, *, expected_chain=None):
    """Return a validated observation dict or raise TransactionValidationError.

    The caller must fetch tx from a trusted, authenticated Tidecoin node and
    separately verify the chain, inclusion, confirmations and reorg status.
    This function cannot prove any of those properties.
    """
    if not isinstance(tx, dict):
        raise TransactionValidationError("Decoded transaction must be an object")
    txid = tx.get("txid")
    if not isinstance(txid, str) or not TXID.fullmatch(txid):
        raise TransactionValidationError("Invalid transaction ID")
    outputs = tx.get("vout")
    if not isinstance(outputs, list) or not outputs:
        raise TransactionValidationError("Transaction outputs missing")
    # Reject ambiguous duplicate vout indexes and malformed outputs rather than
    # silently ignoring them.
    indexes = set()
    total = 0
    matched = False
    for output in outputs:
        if not isinstance(output, dict):
            raise TransactionValidationError("Malformed transaction output")
        n = output.get("n")
        if type(n) is not int or n < 0 or n in indexes:
            raise TransactionValidationError("Invalid or duplicate output index")
        indexes.add(n)
        value = _satoshis(output.get("value"))
        script = output.get("scriptPubKey")
        if not isinstance(script, dict):
            raise TransactionValidationError("Missing scriptPubKey")
        # Only accept explicit decoded addresses, never a substring of script.
        addresses = script.get("addresses")
        single = script.get("address")
        if addresses is not None and (not isinstance(addresses, list) or
                                      not all(isinstance(a, str) for a in addresses)):
            raise TransactionValidationError("Invalid addresses")
        if single is not None and not isinstance(single, str):
            raise TransactionValidationError("Invalid address")
        destinations = set(addresses or [])
        if single is not None:
            destinations.add(single)
        if invoice.address in destinations:
            # Multiple destinations are ambiguous for a merchant invoice.
            if len(destinations) != 1:
                raise TransactionValidationError("Ambiguous payment output address")
            matched = True
            total += value
    if not matched or total == 0:
        raise TransactionValidationError("No positive payment to invoice address")
    confirmations = tx.get("confirmations", 0)
    if type(confirmations) is not int or confirmations < 0:
        raise TransactionValidationError("Invalid confirmations")
    return {"txid": txid.lower(),
            "received_tdc": Decimal(total) / Decimal(100_000_000),
            "confirmations": confirmations}
