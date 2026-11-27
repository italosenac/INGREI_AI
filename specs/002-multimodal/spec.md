# Multimodal tutor

- Corrected writing gets a short explanation, example, exercise and a topic-linked curated reference. No model-generated URLs.
- Voice messages only in the authorized group; 1–30 seconds and max 2 MB, 2/minute and 30/day, asynchronous processing.
- Transcribe English and Brazilian Portuguese using managed speech recognition. Clearly distinguish transcript confidence from pronunciation evaluation; no phoneme, prosody or fluency scores without a validated acoustic model.
- Polly US English audio of the corrected sentence; text response survives synthesis failure.
- Private encrypted temporary S3 storage, delete inputs/outputs after processing, one-day lifecycle safety net. No permanent student recordings or transcript database.
- Keep existing webhook, text behavior and expiry. Portuguese-only messages warn, not delete until moderation validation.
- Validate unit tests, actual managed speech services with synthetic sample, and real Telegram test separately. No claim of custom fine-tuning.
