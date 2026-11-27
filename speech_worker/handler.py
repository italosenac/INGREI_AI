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
    stage="input"
    try:
        encoded=event.get("audio","")
        if not isinstance(encoded,str) or len(encoded)>2666672:
            return {"status":"invalid"}
        audio=base64.b64decode(encoded,validate=True)
        if not audio or len(audio)>2000000:
            return {"status":"invalid"}
        stage="decode"
        from faster_whisper.audio import decode_audio
        samples=decode_audio(io.BytesIO(audio),sampling_rate=16000)
        if not 800<=len(samples)<=16000*31:
            return {"status":"invalid_duration"}
        import numpy as np
        if not np.isfinite(samples).all() or float(np.sqrt(np.mean(samples*samples))) < 0.0005:
            return {"status":"uncertain","text":""}
        stage="recognition"
        segments,info=model().transcribe(samples,beam_size=3,task="transcribe",
            vad_filter=False,condition_on_previous_text=False,
            word_timestamps=False,no_speech_threshold=0.6,log_prob_threshold=-1.0)
        stage="decode_segments"
        parts=list(segments)
        text=" ".join(s.text.strip() for s in parts).strip()[:2000]
        # avg_logprob is a model diagnostic, not pronunciation or calibrated accuracy.
        weak=not parts or any(not math.isfinite(s.avg_logprob) or s.avg_logprob < -1.2 for s in parts)
        if not weak and text:
            return {"status":"complete","text":text,"language":info.language}
        # A second English-biased pass only for weak recognition. Never force a
        # result for silence; do not equate these hypotheses with actual words.
        if context is None or context.get_remaining_time_in_millis()>22000:
            alternate_segments,_=model().transcribe(samples,language="en",beam_size=3,
                task="transcribe",vad_filter=False,condition_on_previous_text=False,
                no_speech_threshold=0.6,log_prob_threshold=-1.0)
            alt=" ".join(s.text.strip() for s in alternate_segments).strip()[:1000]
        else:
            alt=""
        return {"status":"uncertain","text":text[:1000],"alternate":alt,"language":info.language}
    except Exception as exc:
        # Only operational diagnostics, never record audio or transcript.
        return {"status":"error","stage":stage,"error_type":type(exc).__name__}
