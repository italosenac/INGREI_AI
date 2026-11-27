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

## Cost optimization release — 2026-11-26 America/Recife
- Worker image whisper-v6, digest sha256:fc6ce9b93c10f0a0d8dd5ca86e084d0a0962bb2c4a5df97712af60f361a159bd. Faster-Whisper + Piper 1.8.0 local neural synthesis, LJSpeech US English medium voice, public-domain training dataset.
- CodeBuild completed, offline synthesis/recognition round trip passed. ECR scan reports zero HIGH/CRITICAL, six MEDIUM and one LOW. Both CloudFormation stacks UPDATE_COMPLETE.
- Main tutor no longer calls Polly or has polly:SynthesizeSpeech permission. Private worker produced MP3; integrated Piper -> Whisper -> tutor test returned the original sample sentence and 9004 bytes of playback. Main Lambda selftest 35/35 passed.
- Local fixed-example grammar rules and greetings bypass Bedrock; novel/context-dependent input still uses Nova Lite. No student-message cache or external free speech API.
- Voice quota increased to 120/day, 5/minute; 30 seconds per note. Playback command remains 30/day. Text quota 500/day. These are group-level limits, not a financial hard cap.
- Estimated recurring cost before tax/FX markup, 30 days, 30–60 notes and same number of texts/day: approximately USD 0.79–2.08, assuming 850 input/130 output tokens per modeled turn, 3–12s typical recognition, 1.5–3s synthesis, 7–17s tutor worker and available or exhausted shared Lambda free tier. ECR/Secrets Manager/DynamoDB/logs estimated; actual cost varies. One-off builds excluded. No actual billing attribution established.
- No additional always-on server or GPU. A real learner voice-note and Telegram playback after this version still require user verification. Custom model training and acoustic pronunciation scoring remain unimplemented.

## Long-text and language review release
- Reproduced the original five-paragraph synthetic test: 550 output tokens caused stopReason=max_tokens; the previous adapter discarded the truncated JSON.
- New passage route accepts up to 4096 characters, batches sections at 1600 characters, adapts output budgets up to 4000 tokens, validates section completeness and retries failed multi-section batches once with smaller groups. Long review is queued asynchronously, with an acknowledgement and separate quota of 2/minute, 20/day. Existing short-text and incoming voice paths retained.
- CloudFormation UPDATE_COMPLETE, Lambda timeout 150 seconds, 47/47 selftests passed. Actual model integration test returned five corrected sections, conversational feedback and five pronunciation buttons via mocked Telegram delivery. Some individual explanations remained incomplete; no claim of perfect linguistic accuracy.
- Six real Nova Lite language examples classified correctly: three Portuguese-only, one mixed, one phonetic English and one correct English. Conservative local evidence guard and fixed Portuguese greetings provide additional protection against false praise; not a comprehensive language detector.
- No new paid service; long inputs consume more Bedrock tokens and Lambda time. Existing playback quota retained. Real group delivery still needs confirmation. No document attachments or unlimited-length messages supported.

## Multilingual English-immersion release
- CloudFormation UPDATE_COMPLETE; 52/52 unit tests passed. Eight real model/backend examples with simulated Telegram transport passed: Spanish, Portuguese, French, German, Japanese translated into English; mixed and phonetic English corrected; correct English praised. Both reported screenshot examples reproduced successfully.
- Conservative multilingual lexical/script evidence and source-language classification; bounded translation repair only on inconsistent results. No new external service. Not comprehensive language identification or a guarantee of linguistic perfection.
- New pronunciation buttons v2 point to English output; legacy v1 buttons retired, users must resend to receive a new button. /listen validates/corrects/translates its input. Voice correction path retains existing recognition and playback behavior with additional language guards. Long-text path remains enabled. Actual group click and fresh audio synthesis of the Spanish translation not verified in this release.

## Natural English equivalence release — 2026-11-27
- CloudFormation UPDATE_COMPLETE; 59/59 Lambda selftests passed. Deployment template commit c37ee63d3cf23dd123b63fe8b6638c7682c3d7e0.
- Natural-equivalence guidance applies to short text, passage review, speech analysis and translation repair. Narrow curated idioms and vocative rules run locally; no new paid service or learner cache. Known literal calques trigger at most one bounded semantic repair, then clarification if still unresolved.
- Final backend evaluation: 13 examples, 9 local rules and 4 managed model paths. All 13 displayed expected natural English correction or confirmation; the possessive dog question was translated correctly, but the conversational reply incorrectly implied looking for the user's dog. Conversational grounding and generalization to unseen idioms remain imperfect. No claim of perfect translation accuracy.
- Reported Portuguese vocative and disappointment idiom now render natural English with matching pronunciation target. Transport was simulated; real Telegram delivery and playback for this release not verified. No changes to infrastructure size or quotas; occasional semantic repair can increase token usage.
