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
