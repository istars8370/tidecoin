"""Offline-only payment state model. No wallet, network, or RPC access."""
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Optional
import re

TXID_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class Status(str, Enum):
    PENDING = "pending"
    UNDERPAID = "underpaid"
    CONFIRMING = "confirming"
    PAID = "paid"
    EXPIRED = "expired"
    REVIEW = "review_required"


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    address: str
    amount_tdc: Decimal
    expires_at: int
    created_at: int
    status: Status = Status.PENDING
    txid: Optional[str] = None
    received_tdc: Decimal = Decimal("0")
    confirmations: int = 0


def amount(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid TDC amount") from exc
    if not result.is_finite() or result <= 0 or result.as_tuple().exponent < -8:
        raise ValueError("TDC amount must be positive with at most 8 decimal places")
    return result


def new_invoice(invoice_id, address, amount_tdc, created_at, expires_at):
    if not invoice_id or not isinstance(invoice_id, str):
        raise ValueError("Invoice ID required")
    if not isinstance(address, str) or not address.strip():
        raise ValueError("Nonempty address required; validate against the live chain before use")
    if not isinstance(created_at, int) or not isinstance(expires_at, int) or expires_at <= created_at:
        raise ValueError("Invalid invoice time range")
    return Invoice(invoice_id, address, amount(amount_tdc), expires_at, created_at)


def observe(invoice, txid, received_tdc, confirmations, now, required_confirmations=6):
    """Process one externally verified, invoice-address-bound payment observation.

    The caller MUST independently verify txid, address, amount, chain and
    transaction status. This function does not access the blockchain.
    """
    if invoice.status in (Status.PAID, Status.EXPIRED, Status.REVIEW):
        return invoice
    if not isinstance(txid, str) or not TXID_PATTERN.fullmatch(txid):
        raise ValueError("Invalid transaction ID")
    if not isinstance(confirmations, int) or confirmations < 0:
        raise ValueError("Invalid confirmations")
    if not isinstance(required_confirmations, int) or required_confirmations < 1:
        raise ValueError("Invalid confirmation threshold")
    if not isinstance(now, int):
        raise ValueError("Invalid observation time")
    paid = amount(received_tdc)
    if invoice.txid is not None and invoice.txid.lower() != txid.lower():
        return replace(invoice, status=Status.REVIEW)
    if now >= invoice.expires_at and invoice.txid is None:
        return replace(invoice, status=Status.EXPIRED)
    status = (Status.UNDERPAID if paid < invoice.amount_tdc
              else Status.PAID if confirmations >= required_confirmations
              else Status.CONFIRMING)
    return replace(invoice, txid=txid.lower(), received_tdc=paid,
                   confirmations=confirmations, status=status)
