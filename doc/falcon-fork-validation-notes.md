# TIDECOIN Falcon/PQ regression validation — contribution notes

This document records a **fork-only** validation effort. It is not a claim of a security audit or a change to the Tidecoin consensus protocol.

## Scope

Repository: `istars8370/tidecoin`

- Test branch: `test/falcon-sign-retry-boundaries`
- Validation branch: `ci/falcon-fork-validation`
- Workflow: `.github/workflows/falcon-fork-validation.yml`
- Test source: `src/test/pq_random_key_tests.cpp`

## Test coverage

The added `falcon_strict_sign_retry_at_last_attempt` test covers both Falcon-512 and Falcon-1024:

1. Generate a fresh public/private key pair.
2. Force `kFalconSignMaxAttempts - 1` signing failures.
3. Require signing to succeed on the final permitted attempt.
4. Confirm the failure counter is exhausted and the signature is nonempty.
5. Verify the signature against the original message.
6. Reject verification after flipping one message bit.

The existing `falcon_strict_sign_exhausts_failures` test checks rejection after the full retry budget is exhausted.

The fork workflow builds `test_tidecoin` on Ubuntu 24.04 and invokes:

```bash
./build/bin/test_tidecoin --run_test=pq_random_key_tests --log_level=test_suite
./build/bin/test_tidecoin --run_test=pqhd_keygen_tests --log_level=test_suite
./build/bin/test_tidecoin --run_test=pq_multisig_tests --log_level=test_suite
```

## Observed CI history

A contributor-supplied GitHub Actions screenshot showed four runs on the validation branch:

- #1: success, initial isolated validation.
- #2: not marked successful, expanded PQHD/multisig validation.
- #3: success, checkout action update.
- #4: success, Falcon-1024 strict signing exhaustion coverage.

These statuses come from a screenshot. **Run IDs, exact job logs, assertion counts and tested commit SHA have not yet been independently retrieved**. Do not treat this document as evidence of passing every individual assertion until the run logs are inspected.

## Proposed upstream contribution

Keep upstream changes small and reviewable:

- **Test PR**: `src/test/pq_random_key_tests.cpp` only, from `test/falcon-sign-retry-boundaries`.
- **Documentation PR**: `doc/fuzzing.md` only, from `docs/clarify-libfuzzer-nosan-path`.
- **Fork-only CI**: Keep the custom workflow in the fork unless upstream maintainers explicitly request it. The official repository already has extensive CI.

Suggested test PR title: `test: Cover Falcon strict signing final retry boundary`

Suggested PR summary:

> Add a regression test for the last permitted Falcon strict-signing attempt in both Falcon-512 and Falcon-1024. The test verifies a valid signature on the original message and rejects a one-bit-modified message. No consensus, wallet, or cryptographic implementation code is changed.

## Before requesting upstream review

- [ ] Confirm the exact successful workflow run URL and commit SHA.
- [ ] Inspect each test step and assert that all three suites ran, rather than merely compiling.
- [ ] Check whether upstream already has equivalent tests.
- [ ] Confirm the test branch is current with upstream master.
- [ ] Open upstream PR only after contributor approval.
