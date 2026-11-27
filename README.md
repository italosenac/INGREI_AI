# TechVerse English AI

English immersion tutor for Brazilian learners in one authorized Telegram group.

## Features
- Contextual English spelling, grammar, mixed-language and phonetic-writing corrections using local exact-match teaching rules first and Amazon Nova Lite for novel or ambiguous sentences. No learner-message cache.
- Corrections include an explanation, example, short exercise and a curated topic-linked study resource.
- Voice notes (1–30 seconds, up to 2 MB) use private Faster-Whisper Base INT8 on AWS Lambda. No Amazon Transcribe dependency or per-minute Transcribe charge. Local Piper TTS uses an English US LJSpeech medium voice (public-domain training dataset); no Polly calls or managed TTS charge.
- Speech feedback explains the recognized sentence, suggests corrections and can send a Piper pronunciation example. Weak audio may trigger a bounded English-biased second recognition pass and tentative meaning alternatives, rather than discarding partial words. Accepted voice notes get an acknowledgement, and rejection notices are rate-limited. Transcription is not a validated pronunciation, fluency or CEFR score.
- Commands: /help, /rules, /learn, /learn past, /listen I love English; reply to a previous voice note with /retry.
- Portuguese-only messages receive a warning; deletion is disabled until independent moderation validation.
- No persistent student recordings, transcript database or training on learner messages. Telegram and AWS still process messages in accordance with their own service terms. Group ID and credentials are in Secrets Manager, never in GitHub.

## Deployment
- Region: us-east-1. Stacks: techverse-english-mvp-v2, techverse-whisper-build, techverse-whisper-worker.
- Main Lambda webhook uses a secret header and group-ID allowlist. Private speech Lambda has no public URL or access to the Telegram credential.
- Build once on demand with CodeBuild, publish to private ECR, deploy by immutable image digest. Faster-Whisper 1.2.1, PyAV 18.1.0 and Piper 1.8.0 are pinned; the model weights are checksum-verified. No GPU or provisioned concurrency.
- Inference limits: 20/minute and 500/day for the group. Voice: 5/minute and 120/day; playback: 2/minute and 30/day. Voice has its own inference allowance, separate from text. Fixed windows, not a financial hard cap.
- AWS Lambda, Bedrock, ECR, Secrets Manager, DynamoDB, logging and occasional builds may incur charges. No guarantee of zero cost.
- Expiry: 2027-05-27T00:00:00Z. Processing stops at expiry; separately remove project resources after the six-month period to stop ongoing storage and secret charges.

## Tests
Run locally: `python -m unittest discover -s tests -v`.
Private IAM invocation: `{"operation":"selftest"}` for the main Lambda, `{"operation":"speech_selftest"}` for synthetic speech integration and `{"operation":"health"}` for the private worker.
Unit tests use mocks for Telegram; real voice delivery in the group must be verified separately. Fine-tuning of model weights has not been performed.

See specs/001-mvp/spec.md, specs/002-multimodal/spec.md and infra/ for specifications and deployment templates.

The Piper engine is GPL-licensed; model card and licensing information are packaged in the private worker. See https://github.com/OHF-Voice/piper1-gpl and https://huggingface.co/rhasspy/piper-voices/blob/v1.0.0/en/en_US/ljspeech/medium/MODEL_CARD. Open-source inference still consumes AWS compute. The 120/day audio allowance is shared by the group, and individual audio notes remain limited to 30 seconds.

## Conversation mode
The tutor replies naturally in English to eligible text and voice, even when the grammar is correct. Ordinary profanity alone is not a grammar error; the tutor answers without retaliating. Genuine errors still receive a correction and learning resources. Unknown or ambiguous speech receives clarification. Group isolation, rate limits, platform safeguards and no-logging rules remain in force. `/retry` is for a previous voice note, not a text message.
