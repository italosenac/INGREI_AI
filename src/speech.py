"""Bounded, asynchronous speech tutor. No raw student data in logs."""
import datetime
import json
import os
import re
import urllib.request
import uuid
from .knowledge import lesson, safe_text, CATALOG, conversation
from .policy import decide
from .inference import analyze_voice

def voice_allowed(voice):
    return (isinstance(voice,dict) and isinstance(voice.get("file_id"),str)
            and type(voice.get("duration")) is int and 1<=voice["duration"]<=30
            and type(voice.get("file_size",0)) is int and 0<=voice.get("file_size",0)<=2000000)

def synthesize_bytes(text, client=None):
    import base64
    if not isinstance(text,str) or not text.strip(): raise ValueError("empty speech text")
    if client is None:
        import boto3
        from botocore.config import Config
        client=boto3.client("lambda",config=Config(connect_timeout=3,read_timeout=75,retries={"total_max_attempts":1}))
    result=client.invoke(FunctionName=os.environ["WHISPER_FUNCTION"],InvocationType="RequestResponse",
        Payload=json.dumps({"operation":"synthesize","text":text.strip()[:500]}).encode())
    with result["Payload"] as stream:
        data=json.load(stream)
    if result.get("FunctionError") or data.get("status")!="complete" or data.get("format")!="mp3":
        raise RuntimeError("local speech synthesis failed")
    audio=base64.b64decode(data["audio"],validate=True)
    if not 100<len(audio)<=2000000: raise ValueError("invalid synthesized audio")
    return audio

def send_voice(token, group_id, message_id, text):
    audio=synthesize_bytes(text)
    boundary=uuid.uuid4().hex
    chunks=[]
    for name,value in {"chat_id":str(group_id),"reply_parameters":json.dumps({"message_id":message_id}),"caption":"Listen and repeat (US English)"}.items():
        chunks.append(("--"+boundary+"\r\nContent-Disposition: form-data; name=\""+name+"\"\r\n\r\n"+value+"\r\n").encode())
    chunks.append(("--"+boundary+"\r\nContent-Disposition: form-data; name=\"voice\"; filename=\"practice.mp3\"\r\nContent-Type: audio/mpeg\r\n\r\n").encode()+audio+b"\r\n")
    chunks.append(("--"+boundary+"--\r\n").encode())
    req=urllib.request.Request("https://api.telegram.org/bot"+token+"/sendVoice",data=b"".join(chunks),
        headers={"Content-Type":"multipart/form-data; boundary="+boundary})
    with urllib.request.urlopen(req,timeout=10) as response:
        payload=json.load(response)
        if not payload.get("ok"): raise RuntimeError("voice send failed")
        return payload["result"]["message_id"]

def transcribe_bytes(audio, client=None):
    """Invoke the private Whisper worker; no S3 or external transcription API."""
    import base64
    if not isinstance(audio,bytes) or not 0<len(audio)<=2000000:
        raise ValueError("invalid audio size")
    if client is None:
        import boto3
        from botocore.config import Config
        client=boto3.client("lambda",config=Config(connect_timeout=3,read_timeout=75,retries={"total_max_attempts":1}))
    result=client.invoke(FunctionName=os.environ["WHISPER_FUNCTION"],InvocationType="RequestResponse",
        Payload=json.dumps({"audio":base64.b64encode(audio).decode("ascii")}).encode())
    with result["Payload"] as stream:
        data=json.load(stream)
    if result.get("FunctionError") or not isinstance(data,dict):
        raise RuntimeError("speech worker failed")
    if data.get("status")=="invalid_duration":
        return "",None
    if data.get("status")=="uncertain":
        primary=data.get("text","")
        alternate=data.get("alternate","")
        candidates=list(dict.fromkeys(x.strip()[:900] for x in (primary,alternate) if isinstance(x,str) and x.strip()))
        return " | ".join(candidates),0.4 if candidates else None
    if data.get("status")!="complete" or not isinstance(data.get("text"),str):
        raise RuntimeError("speech worker rejected recording")
    return data["text"].strip()[:2000],None

def voice_feedback(text, confidence, infer=analyze_voice):
    if not text:
        return "I heard your recording, but I couldn't recognize the words reliably. Try again slowly, one short phrase at a time. You can also type what you meant.\n\nSpeaking practice: "+CATALOG["pronunciation"][1], ""
    tentative=confidence is not None and confidence<0.65
    raw=infer(("Uncertain speech hypotheses (not confirmed): "+text if tentative else text)[:2000])
    d=decide(raw)
    prefix=("Possible words I recognized: " if tentative else "What I understood: ")+safe_text(text,1000)+"\n\n"
    if not tentative and conversation(raw): prefix+=conversation(raw)+"\n\n"
    if d.action=="clarify":
        try:
            data=json.loads(raw)
            possibilities=[safe_text(data.get(k),200) for k in ("possible_meaning","alternate_meaning")]
        except (ValueError,AttributeError,TypeError):
            possibilities=[]
        suggestions=list(dict.fromkeys(p for p in possibilities if p))
        hint="Possible meanings (not confirmed):\n"+"\n".join("- "+p for p in suggestions)+"\n\n" if suggestions else ""
        return prefix+hint+"Which meaning did you intend? Please repeat slowly or type your intended sentence.\n\nSpeaking practice: "+CATALOG["pronunciation"][1], suggestions[0] if len(suggestions)==1 else ""
    if d.action in ("correct","warn"):
        if tentative:
            return prefix+"My best guess (please confirm): "+safe_text(d.correction,1000)+"\n\n"+lesson(raw,d)+"\n\nDoes this match what you meant? Listen and repeat if so.",safe_text(d.correction,1000)
        return prefix+lesson(raw,d)+"\n\nListen and repeat. Transcription is not a pronunciation score.",safe_text(d.correction,1000)
    if d.action=="allow":
        # An invalid response is not evidence that the sentence is correct.
        try: category=json.loads(raw).get("category")
        except (ValueError,AttributeError): category=None
        if category=="correct" and tentative:
            return prefix+"My best guess: "+safe_text(text.split(" | ")[0],900)+"\nIs that what you meant? Please confirm.\n\nSpeaking practice: "+CATALOG["pronunciation"][1],""
        if category=="correct":
            return prefix+"Your transcribed sentence looks correct. Listen and repeat.\n\nListening practice: "+CATALOG["listening"][1]+"\n\nTranscription is not a pronunciation score.",safe_text(text,1000)
    return prefix+"I couldn't assess the sentence reliably. Please try another recording or type what you meant.\n\nSpeaking practice: "+CATALOG["pronunciation"][1], ""

def process_voice(token, group_id, message, telegram):
    voice=message["voice"]
    if not voice_allowed(voice): return "invalid"
    file=telegram(token,"getFile",{"file_id":voice["file_id"]})
    path=file.get("file_path","")
    if not re.fullmatch(r"[A-Za-z0-9_./-]+",path) or ".." in path or path.startswith("/"):
        raise ValueError("invalid audio path")
    with urllib.request.urlopen("https://api.telegram.org/file/bot"+token+"/"+path,timeout=10) as response:
        audio=response.read(2000001)
    if len(audio)>2000000 or not audio.startswith(b"OggS"):
        raise ValueError("unsupported audio")
    text,confidence=transcribe_bytes(audio)
    reply,spoken=voice_feedback(text,confidence)
    telegram(token,"sendMessage",{"chat_id":group_id,"text":reply[:3500],
        "reply_parameters":{"message_id":message["message_id"],"allow_sending_without_reply":True},
        "link_preview_options":{"is_disabled":True}})
    if spoken:
        try:
            send_voice(token,group_id,message["message_id"],spoken)
        except Exception:
            # Keep successful text feedback if audio playback fails.
            return "text_only"
    return "complete"
