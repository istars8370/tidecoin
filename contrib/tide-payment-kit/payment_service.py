"""Conservative orchestration for one confirmed Tidecoin transaction.

This is a *candidate* assessment, NEVER authorization to ship goods.
No key handling, broadcast, refunds, or automatic settlement.
"""
import time
from decimal import Decimal

from payment_journal import JournalError
from payment_model import Invoice, amount, TXID_PATTERN
from rpc_client import RPCError, inspect_payment


class PaymentServiceError(ValueError):
    pass


def assess_payment(journal, rpc, invoice, txid, expected_chain,
                   required_confirmations=6, observed_at=None):
    """Register an invoice, inspect a canonical transaction and journal the result.

    Only RPC-confirmed transactions are supported. An RPC failure must never be
    treated as proof of a reorg: call record_orphan only after independent proof.
    An expired invoice is never automatically marked as candidate_paid.
    """
    if not isinstance(invoice, Invoice):
        raise PaymentServiceError("Invoice object required")
    if not isinstance(txid, str) or not TXID_PATTERN.fullmatch(txid):
        raise PaymentServiceError("Invalid transaction ID")
    if type(required_confirmations) is not int or required_confirmations < 1:
        raise PaymentServiceError("Invalid confirmation threshold")
    if type(observed_at) is not int and observed_at is not None:
        raise PaymentServiceError("Invalid observation timestamp")
    now = int(time.time()) if observed_at is None else observed_at
    journal.register(invoice)

    # A successful inspection checks the selected chain, active block,
    # confirmation count and exact decoded output address.
    observation = inspect_payment(rpc, invoice, txid, expected_chain)
    received = amount(observation["received_tdc"])
    confirmations = observation["confirmations"]
    blockhash = observation["blockhash"]

    prior = journal.history(invoice.invoice_id)
    # Never silently approve a payment after contradictory observations.
    prior_txids = {row["txid"] for row in prior}
    prior_hashes = {row["blockhash"] for row in prior
                    if row["txid"] == txid.lower() and row["blockhash"]}
    if (now >= invoice.expires_at or received < invoice.amount_tdc
            or (prior_txids and prior_txids != {txid.lower()})
            or (prior_hashes and blockhash not in prior_hashes)
            or journal.needs_review(invoice.invoice_id)):
        state = "review_required"
    elif confirmations < required_confirmations:
        state = "confirming"
    else:
        state = "candidate_paid"

    journal.record(invoice.invoice_id, observation["txid"], received,
                   confirmations, blockhash, state, observed_at=now)
    return {
        "invoice_id": invoice.invoice_id,
        "txid": observation["txid"],
        "state": state,
        "received_tdc": str(received),
        "confirmations": confirmations,
        "required_confirmations": required_confirmations,
        "needs_review": journal.needs_review(invoice.invoice_id),
        "settlement_authorized": False,
    }


def record_orphan(journal, invoice_id, txid, last_amount_tdc,
                  observed_at=None):
    """Manual evidence-based reorg marker; never infer from a transient RPC error.

    Caller must independently establish that a previously confirmed tx's block
    is no longer canonical. This function itself cannot establish chain status.
    """
    history = journal.history(invoice_id)
    txid = txid.lower() if isinstance(txid, str) else txid
    if not any(row["txid"] == txid and row["blockhash"] for row in history):
        raise PaymentServiceError("No prior confirmed observation for txid")
    return journal.record(invoice_id, txid, last_amount_tdc, 0, None,
                          "orphaned", observed_at=observed_at)
