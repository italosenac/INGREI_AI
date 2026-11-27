# Deployment validation — 2026-11-26

- CloudFormation stack `techverse-english-mvp-v2`: UPDATE_COMPLETE.
- Lambda `techverse-english-tutor`: selftest 10 tests, 0 failures, 0 errors after endpoint update.
- Telegram activation operation: active; administrator deletion permission true.
- Subsequent discovery confirmed existing webhook; two deduplication records observed. These do not establish successful reply delivery.
- Group restricted by numeric ID in Secrets Manager (not included here).
- Public HTTPS transport endpoint uses application-level Telegram secret authentication; direct IAM invocation remains separate. Paid inference limits: 20/minute, 500/day.
- Real user-visible correction delivery remains to be confirmed in group. Portuguese-only messages warn, not delete, pending independent validation. Custom fine-tuning not performed. Do not claim end-to-end or model-quality acceptance from unit tests.
- Code expiry stops inference; stack teardown is separately required to stop all ongoing charges.

## Multimodal release — 2026-11-26 America/Recife

- Dedicated CodeBuild/ECR image and private Lambda worker; no Amazon Transcribe calls or permission in tutor.
- Faster-Whisper Base INT8, CPU, verified weight SHA-256. PyAV 19 incompatibility reproduced (TypeError in decode), fixed by pinning 18.1.0. Build v3 passed offline read-only container synthetic speech recognition.
- Actual Opus speech samples synthesized by Polly and recognized verbatim in English and Brazilian Portuguese. Main synthetic speech pipeline returned correct transcript, study link and playback text.
- Main Lambda selftest: 26/26 passed, zero failures and errors. Tests cover group isolation, voice limits, invalid model output, curated links, command routing and mocked Whisper integration. Verified after enabling voice.
- Telegram webhook remains registered; both Lambdas active; VOICE_INPUT_ENABLED=true. Private delivery selftest returned Telegram confirmation for one synthetic text and one voice message. Real learner microphone input still requires confirmation.
- Candidate linguistic evaluation: 10 actual Nova Lite calls; nine category matches. Case 18 reference changes bought to received; model preserves bought, so reference requires review. Greeting topic and pronunciation links added. This is not a representative accuracy benchmark.
- ECR v3 scan showed four HIGH findings (two RPM CVEs across two packages), six MEDIUM, one LOW; patched ALAS2023-2026-3430 in v4, build and scan complete: zero reported HIGH/CRITICAL, six MEDIUM and one LOW. Basic ECR scan is not a comprehensive application-dependency audit.
- Limits: 500 inference calls/day and 20/minute, voice/playback 30/day and 2/minute per group. Lambda and CodeBuild on demand, no GPU or server continuously running. Charges still possible for compute, model calls, Polly, ECR, secret, database, logs and build. Expiry stops processing, not all recurring charges.
- No custom fine-tuning, phoneme scoring or Portuguese automatic deletion yet. No audio/transcripts stored by application. The old temporary audio bucket remains in the stack but is not used by the new recognition path.
