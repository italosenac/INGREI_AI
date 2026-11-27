"""Bounded, asynchronous speech tutor. No raw student data in logs."""
import datetime
import json
import os
import re
import time
import urllib.request
import uuid
from .knowledge import lesson, safe_text, CATALOG
from .policy import decide
from .inference import analyze

def voice_allowed(voice):
    return (isinstance(voice,dict) and isinstance(voice.get("file_id"),str)
            and type(voice.get("duration")) is int and 1<=voice["duration"]<=30
            and type(voice.get("file_size",0)) is int and 0<=voice.get("file_size",0)<=2000000)

def send_voice(token, group_id, message_id, text):
    import boto3
    result=boto3.client("polly").synthesize_speech(Engine="neural",VoiceId="Joanna",
        LanguageCode="en-US",OutputFormat="mp3",Text=text[:1000])
    with result["AudioStream"] as stream:
        audio=stream.read(2000000)
    boundary=uuid.uuid4().hex
    chunks=[]
    for name,value in {"chat_id":str(group_id),"reply_parameters":json.dumps({"message_id":message_id}),"caption":"Listen and repeat (US English)"}.items():
        chunks.append(("--"+boundary+"\r\nContent-Disposition: form-data; name=\""+name+"\"\r\n\r\n"+value+"\r\n").encode())
    chunks.append(("--"+boundary+"\r\nContent-Disposition: form-data; name=\"voice\"; filename=\"practice.mp3\"\r\nContent-Type: audio/mpeg\r\n\r\n").encode()+audio+b"\r\n")
    chunks.append(("--"+boundary+"--\r\n").encode())
    req=urllib.request.Request("https://api.telegram.org/bot"+token+"/sendVoice",data=b"".join(chunks),
        headers={"Content-Type":"multipart/form-data; boundary="+boundary})
    with urllib.request.urlopen(req,timeout=10) as response:
        if not json.load(response).get("ok"): raise RuntimeError("voice send failed")

def transcribe_bytes(audio):
    import boto3
    bucket=os.environ["AUDIO_BUCKET"]
    job="techverse-english-"+uuid.uuid4().hex
    source="input/"+job+".ogg"
    output="output/"+job+".json"
    s3=boto3.client("s3")
    transcribe=boto3.client("transcribe")
    started=False
    try:
        s3.put_object(Bucket=bucket,Key=source,Body=audio,ContentType="audio/ogg")
        transcribe.start_transcription_job(TranscriptionJobName=job,MediaFormat="ogg",
            Media={"MediaFileUri":"s3://"+bucket+"/"+source},
            IdentifyMultipleLanguages=True,LanguageOptions=["en-US","en-GB","pt-BR"],
            OutputBucketName=bucket,OutputKey=output)
        started=True
        deadline=time.monotonic()+105
        while time.monotonic()<deadline:
            state=transcribe.get_transcription_job(TranscriptionJobName=job)["TranscriptionJob"]["TranscriptionJobStatus"]
            if state=="FAILED": raise RuntimeError("transcription failed")
            if state=="COMPLETED":
                obj=s3.get_object(Bucket=bucket,Key=output)
                with obj["Body"] as body: data=json.load(body)
                results=data["results"]
                text=" ".join(x["transcript"] for x in results.get("transcripts",[])).strip()
                scores=[float(i["alternatives"][0]["confidence"]) for i in results.get("items",[])
                        if i.get("type")=="pronunciation" and i.get("alternatives") and "confidence" in i["alternatives"][0]]
                return text, (sum(scores)/len(scores) if scores else None)
            time.sleep(3)
        raise TimeoutError("transcription timed out")
    finally:
        if started:
            try: transcribe.delete_transcription_job(TranscriptionJobName=job)
            except Exception: pass
        for key in (source,output):
            try: s3.delete_object(Bucket=bucket,Key=key)
            except Exception: pass

def voice_feedback(text, confidence, infer=analyze):
    if not text or confidence is not None and confidence<0.65:
        return "I couldn't understand the recording clearly. Please try again slowly in English.", ""
    raw=infer(text[:2000])
    d=decide(raw)
    prefix="What I understood: "+safe_text(text,1000)+"\n\n"
    if d.action=="clarify":
        return prefix+"Could you say that another way?", ""
    if d.action in ("correct","warn"):
        return prefix+lesson(raw,d)+"\n\nListen and repeat. Transcription is not a pronunciation score.",safe_text(d.correction,1000)
    if d.action=="allow":
        # An invalid response is not evidence that the sentence is correct.
        try: category=json.loads(raw).get("category")
        except (ValueError,AttributeError): category=None
        if category=="correct":
            return prefix+"Your transcribed sentence looks correct. Listen and repeat.\n\nListening practice: "+CATALOG["listening"][1]+"\n\nTranscription is not a pronunciation score.",safe_text(text,1000)
    return prefix+"I couldn't assess the sentence reliably. Please try another recording.", ""

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
        "reply_parameters":{"message_id":message["message_id"],"allow_sending_without_reply":False},
        "link_preview_options":{"is_disabled":True}})
    if spoken: send_voice(token,group_id,message["message_id"],spoken)
    return "complete"
