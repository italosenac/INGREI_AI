# TechVerse English AI

English immersion tutor for Brazilian learners in one authorized Telegram group.

## Features
- Contextual English spelling, grammar, mixed-language and phonetic-writing corrections using Amazon Nova Lite with Brazilian learner guidance.
- Corrections include an explanation, example, short exercise and a curated topic-linked study resource.
- Voice notes (1–30 seconds, up to 2 MB) use private Faster-Whisper Base INT8 on AWS Lambda. No Amazon Transcribe dependency or per-minute Transcribe charge.
- Speech feedback explains the recognized sentence, suggests corrections and can send a Polly pronunciation example. Weak audio may trigger a bounded English-biased second recognition pass and tentative meaning alternatives, rather than discarding partial words. Accepted voice notes get an acknowledgement, and rejection notices are rate-limited. Transcription is not a validated pronunciation, fluency or CEFR score.
- Commands: /help, /rules, /learn, /learn past, /listen I love English; reply to a previous voice note with /retry.
- Portuguese-only messages receive a warning; deletion is disabled until independent moderation validation.
- No persistent student recordings, transcript database or training on learner messages. Telegram and AWS still process messages in accordance with their own service terms. Group ID and credentials are in Secrets Manager, never in GitHub.

## Deployment
- Region: us-east-1. Stacks: techverse-english-mvp-v2, techverse-whisper-build, techverse-whisper-worker.
- Main Lambda webhook uses a secret header and group-ID allowlist. Private speech Lambda has no public URL or access to the Telegram credential.
- Build once on demand with CodeBuild, publish to private ECR, deploy by immutable image digest. Faster-Whisper 1.2.1 and PyAV 18.1.0 are pinned; the model weights are checksum-verified. No GPU or provisioned concurrency.
- Inference limits: 20/minute and 500/day for the group. Voice: 5/minute and 30/day; playback: 2/minute and 30/day. Voice has its own inference allowance, separate from text. Fixed windows, not a financial hard cap.
- AWS Lambda, Bedrock, Polly, ECR, Secrets Manager, DynamoDB, logging and occasional builds may incur charges. No guarantee of zero cost.
- Expiry: 2027-05-27T00:00:00Z. Processing stops at expiry; separately remove project resources after the six-month period to stop ongoing storage and secret charges.

## Tests
Run locally: `python -m unittest discover -s tests -v`.
Private IAM invocation: `{"operation":"selftest"}` for the main Lambda, `{"operation":"speech_selftest"}` for synthetic speech integration and `{"operation":"health"}` for the private worker.
Unit tests use mocks for Telegram; real voice delivery in the group must be verified separately. Fine-tuning of model weights has not been performed.

See specs/001-mvp/spec.md, specs/002-multimodal/spec.md and infra/ for specifications and deployment templates.
