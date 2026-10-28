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
