# TIDE Payment Kit v0.1 — offline prototype

This is an **experimental payment state model**, not a payment processor.
It neither connects to Tidecoin RPC nor validates blockchain payments.
No real TDC should be accepted based on this code.

## Scope

- Positive fixed-precision (up to 8 decimal places) TDC invoice amounts
- Invoice IDs and expiry timestamps
- Single-transaction state transitions: pending, underpaid, confirming, paid,
  expired and review_required
- Configurable confirmation threshold (default: 6; not a guarantee of finality)
- Offline unit tests

## Run offline tests

From the repository root:

```sh
python3 -m unittest discover -s contrib/tide-payment-kit -p 'test_*.py' -v
```

On Windows PowerShell:

```powershell
py -3 -m unittest discover -s contrib/tide-payment-kit -p "test_*.py" -v
```

## Important limitations

- `observe()` accepts a **trusted external observation**. It does not prove
  that a transaction exists, pays the expected address, or is on the correct
  chain. Do not use it for settlement without independent verification.
- Addresses are intentionally **not validated**. An example placeholder is
  used in tests. No funds should be sent to example addresses.
- No exchange rates, fiat settlement, wallet key handling, refunds, database
  persistence, reorganization handling or multi-transaction aggregation.
- A paid invoice is treated as terminal in this simple model. Real payment
  processing requires chain reorganization handling and durable event history.
- Offline tests are included but have not yet been executed in CI.

## Next milestones

1. Verify tests in CI.
2. Design an authenticated, local read-only Tidecoin RPC adapter.
3. Validate transaction output address and amount against an invoice.
4. Add idempotent persistence and reconciliation for reorgs and partial pays.
5. Test with regtest/testnet before any merchant pilot.

This contribution is developed in a personal fork. It is not endorsed by
Tidecoin maintainers and does not modify Tidecoin consensus or wallet code.

## v0.2: Offline decoded-transaction validation

`transaction_validation.py` checks a decoded transaction object's txid,
unique output indexes, output values, and exact decoded destination address.
It sums multiple outputs to the same invoice address, using decimal arithmetic.
`test_transaction_validation.py` covers valid and invalid examples.

**This is NOT independent blockchain verification.** An attacker can fabricate
a JSON object containing any txid, output, or confirmation count. Only a trusted
Tidecoin node can supply authoritative observations, and the application must
check the correct network, active-chain inclusion, reorgs, and confirmations.
The validator currently relies on decoded address fields, whose exact format
must be checked against Tidecoin's actual RPC responses.

A GitHub Actions workflow was added to execute the offline unit tests on the
personal fork. Workflow execution results have not yet been verified.

Do not accept merchant payments or issue final receipts using this prototype.

## v0.3: Local RPC inspection prototype

`rpc_client.py` provides a restricted local JSON-RPC client for
`getblockchaininfo`, `getrawtransaction` and `getblockheader`.
It requires an explicit expected network, checks a transaction's block hash,
compares transaction and active-chain header confirmation counts, and passes
decoded outputs to the offline validator.

**Do not use for real merchant settlement.** The code has not been tested
against a real Tidecoin node. A transaction index may be required to query
arbitrary confirmed transactions, depending on node configuration. Actual
Tidecoin RPC response formats and ports still require verification.
The fallback RPC port 8754 is unverified; set `TIDE_RPC_URL` to the actual
local RPC endpoint and use `TIDE_RPC_USER`/`TIDE_RPC_PASSWORD` credentials.
Never expose RPC externally or commit credentials.

There is no automatic invoice settlement or receipt generation.
This prototype cannot handle chain reorganization after a payment was
previously observed, invoice persistence, multiple independent payment
transactions, or guaranteed payment finality. The caller must persist and
reconcile observations against the active chain before any production use.

Run all offline tests:

```sh
python3 -m unittest discover -s contrib/tide-payment-kit -p 'test_*.py' -v
```

The tests are mocked and **have not yet been confirmed passing**.

## v0.4: Durable local observation journal

`payment_journal.py` adds an experimental SQLite-backed append-only
observation history. `test_payment_journal.py` covers idempotent invoice
registration, duplicate transaction claims, persistence after reopening,
and reorganization-related review flags.

The journal deliberately uses `candidate_paid`, **not final settlement**.
A transaction ID may only be claimed by one invoice in this prototype.
Repeated identical observations are ignored; changed observations are appended.
A change of block hash or any orphaned/review event makes
`needs_review(invoice_id)` true. Review flags are conservative and are
not automatically cleared.

**Important:** Journal input is caller-supplied and untrusted unless verified
independently against a healthy authenticated node. This module does not
automatically call `inspect_payment`, does not enforce chain identity, and
does not provide crash-safe multi-node reconciliation, signed receipts, a
complete reorg recovery policy, encryption, or a merchant-ready ledger.
Never use it to release goods or recognize revenue automatically.
Back up and protect the SQLite file: it contains order metadata.


## v0.5 — Conservative integration (prototype)

`payment_service.py` connects invoice registration, read-only RPC transaction
inspection, and SQLite observation journaling. It classifies observations as
`confirming`, `candidate_paid`, or `review_required` and returns
`settlement_authorized: false` **in every case**. This is not a payment
acceptance service. No goods should be released based on this result alone.

`record_orphan` provides an explicit manual reorg marker; **RPC errors are
never interpreted as reorg proof**. Historical contradictions remain flagged
for human review. Only already-confirmed transactions are supported.

Run offline tests from the repository root:

```sh
python -m unittest discover -s contrib/tide-payment-kit -p 'test_*.py' -v
```

**Limitations:** No unique chain-validated invoice address generation, no
transaction discovery, no persistent chain identity, no independent proof of
canonicality, no automatic reorg reconciliation, no settlement approval, and
no real-merchant security audit. Local RPC port and network name must be
verified against the running Tidecoin node. Tests are mocked and do not prove
mainnet compatibility.


## v0.6 — RPC hardening (work in progress)

The v0.6 branch adds a bounded (2 MiB) JSON-RPC response reader, validates
JSON-RPC envelopes and response IDs, avoids including server exceptions in
errors, rejects non-string transaction identifiers and block hashes, and
requires an explicitly configured local RPC endpoint. It also adds offline
mock security tests in `test_rpc_security.py`.

**Source-verified default RPC ports:** upstream
`src/chainparamsbase.cpp` currently specifies mainnet **7585**, testnet
**17585**, regtest **17595**. The earlier prototype fallback **8754 was not
verified and has been removed**. Set `TIDE_RPC_URL` explicitly, e.g.
`http://127.0.0.1:7585` only after checking the node's actual config.
The expected chain string is provided explicitly to the inspection function;
verify its exact value with the running node.

Run tests (from repository root):

```sh
python3 -m unittest discover -s contrib/tide-payment-kit -p 'test_*.py' -v
```

### Read-only node diagnostic checklist (not executed)

1. Start an independently managed, fully synced Tidecoin node with RPC bound
   to loopback; do not expose RPC on the public network.
2. Configure `TIDE_RPC_URL`, `TIDE_RPC_USER` and `TIDE_RPC_PASSWORD`
   outside the repository. Do not put secrets in logs or commits.
3. Confirm `getblockchaininfo` returns expected chain, block height and
   synchronization status; check `initialblockdownload` and headers.
4. With a known historical public transaction ID, test read-only
   `getrawtransaction` and `getblockheader`; verify response shape.
5. If historical transaction lookup fails, investigate `txindex` and the
   node's pruning/configuration before assuming the transaction is absent.
6. Confirm all diagnostics remain read-only. Never use private keys, wallet
   operations, send/broadcast RPCs or merchant funds.

**Unverified:** Local test execution and live-node RPC compatibility have not
been established in this branch. Offline mocks do not establish settlement
safety. A shared payment address across invoices is ambiguous and requires
separate reconciliation design. Chain identity is not persisted in the journal.
There is no merchant-ready settlement approval or automatic reorg recovery.
