# Deployment validation — 2026-11-26

- CloudFormation stack `techverse-english-mvp-v2`: UPDATE_COMPLETE.
- Lambda `techverse-english-tutor`: selftest 10 tests, 0 failures, 0 errors after endpoint update.
- Telegram activation operation: active; administrator deletion permission true.
- Subsequent discovery confirmed existing webhook; two deduplication records observed. These do not establish successful reply delivery.
- Group restricted by numeric ID in Secrets Manager (not included here).
- Public HTTPS transport endpoint uses application-level Telegram secret authentication; direct IAM invocation remains separate. Paid inference limits: 20/minute, 500/day.
- Real user-visible correction delivery remains to be confirmed in group. Portuguese-only messages warn, not delete, pending independent validation. Custom fine-tuning not performed. Do not claim end-to-end or model-quality acceptance from unit tests.
- Code expiry stops inference; stack teardown is separately required to stop all ongoing charges.
