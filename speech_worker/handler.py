"""Private speech-to-text Lambda: no recording or transcript persistence."""
import base64
import io
import math
import os

_MODEL = None

def model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel("/opt/model", device="cpu", compute_type="int8", cpu_threads=2, local_files_only=True)
    return _MODEL

def handler(event, context):
    if event.get("operation") == "health":
        model()
        return {"status":"ready","model":"whisper-base","device":"cpu","compute_type":"int8"}
    try:
        encoded=event.get("audio","")
        if not isinstance(encoded,str) or len(encoded)>2666672:
            return {"status":"invalid"}
        audio=base64.b64decode(encoded,validate=True)
        if not audio or len(audio)>2000000:
            return {"status":"invalid"}
        from faster_whisper.audio import decode_audio
        samples=decode_audio(io.BytesIO(audio),sampling_rate=16000)
        if not 800<=len(samples)<=16000*31:
            return {"status":"invalid_duration"}
        segments,info=model().transcribe(samples,beam_size=3,task="transcribe",
            vad_filter=True,condition_on_previous_text=False,
            word_timestamps=False)
        parts=list(segments)
        text=" ".join(s.text.strip() for s in parts).strip()[:2000]
        # avg_logprob is a model diagnostic, not pronunciation or calibrated accuracy.
        weak=not parts or any(not math.isfinite(s.avg_logprob) or s.avg_logprob < -1.2 for s in parts)
        return {"status":"uncertain" if weak or not text else "complete",
                "text":text if not weak else "", "language":info.language}
    except Exception:
        return {"status":"error"}
