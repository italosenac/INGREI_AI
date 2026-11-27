# TechVerse English AI

English immersion tutor for Brazilian learners in one explicitly authorized Telegram group.

## Status and behavior
- Amazon Nova Lite managed contextual inference with Brazilian English linguistic guidance.
- Correct attempted English, phonetic approximations and mixed messages; warn on Portuguese-only messages. Deletion remains disabled until independent moderation evaluation.
- No persistent student message bodies or names. Deduplication stores update IDs temporarily. No student message training without separate consent.
- This is prompt specialization, not trained custom weights.

## Tests
`python -m unittest discover -s tests -v`

## Private AWS staging
`infra/template.json` defines Lambda, least-privilege IAM, DynamoDB TTL, Secrets Manager and seven-day logs. The Lambda initially has no public URL. Configure the generated secret `ingrei/telegram-mvp` privately with a rotated `TELEGRAM_BOT_TOKEN`, preserve `WEBHOOK_SECRET`, and set `GROUP_ID` only after verifying the correct Telegram group. Private IAM invocation with `{"operation":"discover"}` returns group identifiers and titles only if there is no existing webhook. Use `{"operation":"selftest"}` to run unit tests in the deployed Lambda. Do not expose a public URL until test and group verification gates pass. Configure a webhook URL only with authenticated Telegram secret header and restricted allowed updates. No reserved concurrency because of account quota; add a budget/rate control before activation. The six-month expiry stops processing; delete the dedicated stack after expiry to stop recurring resource charges.

See `specs/001-mvp/spec.md` for acceptance criteria.
