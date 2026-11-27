# TechVerse English Tutor — MVP

- Restrict processing to one configured numeric Telegram group ID.
- Accept correct, informal, ambiguous and attempted English; correct spelling, grammar, phonetic approximations and mixed Portuguese/English without changing intent.
- Portuguese-only messages: initially warn; enable removal only after validation of moderation accuracy.
- Treat learner input as untrusted data; validate structured model output; fail open on uncertainty or outage.
- Authenticate webhook, deduplicate updates, limit requests and apply least privilege.
- No credentials or student conversations in GitHub or logs. No training on student messages without separate consent.
- Managed inference first; fine-tuning separate and measured.
- Six-month deployment window with explicit expiry and shutdown procedure.
- Unit, integration and held-out linguistic tests before production.

## Conversation mode (supersedes silence for correct English)
Reply to eligible human text and voice in English, including correct sentences, questions, compliments and ordinary profanity. Distinguish register from grammar. For errors include pedagogical feedback; for correct input answer naturally without invented corrections. On uncertainty or provider failure offer clarification; preserve group isolation, anti-loop controls and quotas.
