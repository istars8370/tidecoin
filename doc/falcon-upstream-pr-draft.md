# Falcon strict signing regression — proposed upstream PR

**Title:** `test: Cover Falcon strict signing retry boundaries`

## Summary

- Extend the existing strict-signing retry exhaustion test to cover Falcon-1024 as well as Falcon-512.
- Verify that signing fails after all `kFalconSignMaxAttempts` forced failures, and that the test failure counter reaches zero.
- Add a test that signing succeeds on the last permitted retry for both Falcon variants.
- Check the resulting signature verifies for the original message and fails for a one-bit-modified message.

## Why

The upstream exhaustion test only covered Falcon-512. Boundary behavior on the final permitted retry and rejection of a modified message were not explicitly covered by that test file. The added checks exercise the existing API without changing cryptographic, consensus, wallet, or networking implementations.

## Changes

Only `src/test/pq_random_key_tests.cpp` is modified.

## Validation

A fork-only Ubuntu 24.04 GitHub Actions workflow compiles `test_tidecoin` and runs the `pq_random_key_tests`, `pqhd_keygen_tests`, and `pq_multisig_tests` suites.

Contributor-provided screenshots show successful CI runs, but the precise workflow run URL, commit SHA and per-test assertion logs should be linked here before submission.

- [ ] Add successful CI run URL
- [ ] Confirm the successful run's tested SHA includes the proposed changes
- [ ] Confirm all named test suites executed
- [ ] Confirm upstream master has not changed since comparison

## Review notes

The changes are limited to test coverage. The expanded exhaustion test uses a test-only failure counter, and the final-retry test checks both positive and negative verification outcomes. No change to signing implementation is proposed.

## Suggested message to maintainer

Hello, I prepared a small Falcon strict-signing regression test contribution in my fork. It extends exhaustion coverage to Falcon-1024 and adds a final-retry boundary test for both Falcon-512 and Falcon-1024, including signature verification and modified-message rejection. I kept the change limited to one test file. I can submit the PR for review once the CI evidence is linked. Thank you for maintaining Tidecoin.
