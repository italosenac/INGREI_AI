# Multimodal tutor

- Corrected writing gets a short explanation, example, exercise and a topic-linked curated reference. No model-generated URLs.
- Voice messages only in the authorized group; 1–30 seconds and max 2 MB, 2/minute and 30/day, asynchronous processing.
- Transcribe English and Brazilian Portuguese using a private Faster-Whisper Base INT8 Lambda, without Transcribe. Clearly distinguish transcript confidence from pronunciation evaluation; no phoneme, prosody or fluency scores without a validated acoustic model.
- Polly US English audio of the corrected sentence; text response survives synthesis failure.
- In-memory audio processing using a private IAM-invoked worker. No permanent student recordings or transcript database. No third-party audio API.
- Keep existing webhook, text behavior and expiry. Portuguese-only messages warn, not delete until moderation validation.
- Validate unit tests, actual open-source speech recognition with synthetic sample, and real Telegram test separately. No claim of custom fine-tuning.

- Build once on demand; do not provision a continuously running server or GPU. AWS Lambda, ECR, CodeBuild, Polly and Bedrock may still incur charges.
- Keep text service running until verified speech worker and integration tests pass.
