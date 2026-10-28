"""Experimental local SQLite observation journal for Tide Payment Kit.

No funds, wallet keys, or network calls. This is NOT a settlement ledger.
"""
import json
import re
import sqlite3
import time
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
STATES = {"observed", "confirming", "candidate_paid", "review_required", "orphaned"}


class JournalError(ValueError):
    pass


class PaymentJournal:
    def __init__(self, path):
        self.path = str(Path(path))
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS invoices (
                invoice_id TEXT PRIMARY KEY,
                address TEXT NOT NULL,
                amount_tdc TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transaction_claims (
                txid TEXT PRIMARY KEY,
                invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id)
            );
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id TEXT NOT NULL REFERENCES invoices(invoice_id),
                txid TEXT NOT NULL REFERENCES transaction_claims(txid),
                blockhash TEXT,
                confirmations INTEGER NOT NULL,
                amount_tdc TEXT NOT NULL,
                state TEXT NOT NULL,
                observed_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_observations_invoice
                ON observations(invoice_id, id);
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def register(self, invoice):
        # Idempotent registration; conflicting re-use of invoice_id is rejected.
        values = (invoice.invoice_id, invoice.address, str(invoice.amount_tdc),
                  invoice.created_at, invoice.expires_at)
        with self.db:
            existing = self.db.execute(
                "SELECT invoice_id,address,amount_tdc,created_at,expires_at "
                "FROM invoices WHERE invoice_id=?", (invoice.invoice_id,)
            ).fetchone()
            if existing is not None:
                if existing != values:
                    raise JournalError("Invoice ID already belongs to another order")
                return False
            self.db.execute("INSERT INTO invoices VALUES (?,?,?,?,?)", values)
            return True

    def record(self, invoice_id, txid, amount_tdc, confirmations, blockhash,
               state, observed_at=None):
        """Append a trusted external observation; no chain proof is performed."""
        if not isinstance(txid, str) or not HEX64.fullmatch(txid):
            raise JournalError("Invalid transaction ID")
        if blockhash is not None and (not isinstance(blockhash, str)
                                      or not HEX64.fullmatch(blockhash)):
            raise JournalError("Invalid block hash")
        if type(confirmations) is not int or confirmations < 0:
            raise JournalError("Invalid confirmations")
        if state not in STATES:
            raise JournalError("Invalid observation state")
        if type(observed_at) is not int and observed_at is not None:
            raise JournalError("Invalid observation timestamp")
        # Avoid floats, invalid values and excess precision.
        from payment_model import amount
        value = str(amount(amount_tdc))
        txid = txid.lower()
        blockhash = blockhash.lower() if blockhash else None
        timestamp = int(time.time()) if observed_at is None else observed_at
        with self.db:
            if self.db.execute("SELECT 1 FROM invoices WHERE invoice_id=?",
                               (invoice_id,)).fetchone() is None:
                raise JournalError("Invoice not registered")
            owner = self.db.execute("SELECT invoice_id FROM transaction_claims WHERE txid=?",
                                    (txid,)).fetchone()
            if owner is not None and owner[0] != invoice_id:
                raise JournalError("Transaction already claimed by another invoice")
            if owner is None:
                self.db.execute("INSERT INTO transaction_claims VALUES (?,?)",
                                (txid, invoice_id))
            previous = self.db.execute(
                "SELECT blockhash, confirmations, amount_tdc, state FROM observations "
                "WHERE invoice_id=? AND txid=? ORDER BY id DESC LIMIT 1",
                (invoice_id, txid)
            ).fetchone()
            current = (blockhash, confirmations, value, state)
            if previous == current:
                return False
            # Record changes rather than silently overwriting past chain state.
            self.db.execute(
                "INSERT INTO observations "
                "(invoice_id,txid,blockhash,confirmations,amount_tdc,state,observed_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (invoice_id, txid, blockhash, confirmations, value, state, timestamp)
            )
            return True

    def history(self, invoice_id):
        rows = self.db.execute(
            "SELECT txid,blockhash,confirmations,amount_tdc,state,observed_at "
            "FROM observations WHERE invoice_id=? ORDER BY id", (invoice_id,)
        ).fetchall()
        return [dict(zip(("txid", "blockhash", "confirmations", "amount_tdc",
                          "state", "observed_at"), row)) for row in rows]

    def needs_review(self, invoice_id):
        """Conservative flag: any chain-block change or orphan event requires review."""
        entries = self.history(invoice_id)
        if not entries:
            return False
        if any(x["state"] in ("review_required", "orphaned") for x in entries):
            return True
        hashes = {x["blockhash"] for x in entries if x["blockhash"]}
        return len(hashes) > 1
