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
