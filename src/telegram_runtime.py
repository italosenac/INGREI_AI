"""Telegram runtime. No message bodies or secrets are logged."""
import base64
import datetime
import hmac
import json
import os
import urllib.request
from .policy import decide, eligible
from .inference import analyze, review_passage, guard_language, foreign_evidence
from .knowledge import lesson, command_reply, conversation, safe_text, passage_parts, passage_batches, passage_notes, message_chunks, CATALOG
from .speech import process_voice, voice_allowed, send_voice

def telegram(token, method, payload):
    request = urllib.request.Request(
        "https://api.telegram.org/bot" + token + "/" + method,
        data=json.dumps(payload).encode(),
        headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(request, timeout=8) as response:
        result=json.load(response)
    if not result.get("ok"):
        raise RuntimeError("Telegram request rejected")
    return result["result"]

def config():
    import boto3
    secret=boto3.client("secretsmanager").get_secret_value(SecretId=os.environ["SECRET_ARN"])
    return json.loads(secret["SecretString"])

def is_long_text(text):
    return len(text)>450 or len([p for p in text.splitlines() if p.strip()])>=3

def handle_passage(message,group_id,token,send,review=None):
    review=review or review_passage
    parts=passage_parts(message["text"])
    batches=passage_batches(parts)
    results=[]
    replies=[]
    def evaluate(batch):
        try: return review(batch)
        except Exception as exc:
            print("passage_review_failed:"+type(exc).__name__)
            return None
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_pass=list(pool.map(evaluate,batches))
    for batch,data in zip(batches,first_pass):
        if data is None and len(batch)>1:
            mid=len(batch)//2
            groups=[(batch[:mid],evaluate(batch[:mid])),(batch[mid:],evaluate(batch[mid:]))]
        else:
            groups=[(batch,data)]
        for group,data in groups:
            if data is None:
                results.extend((p,None) for p in group)
                continue
            reply=safe_text(data.get("conversational_reply"),700)
            if reply: replies.append(reply)
            results.extend(zip(group,data["paragraphs"]))
    def post(text,target=""):
        payload={"chat_id":group_id,"text":text,
            "reply_parameters":{"message_id":message["message_id"],"allow_sending_without_reply":True},
            "link_preview_options":{"is_disabled":True}}
        if target and len(target)<=500 and not foreign_evidence(target):
            payload["text"]+="\n\n🔊 Pronunciation: "+target+"\nWould you like to hear the pronunciation?"
            payload["reply_markup"]={"inline_keyboard":[[{"text":"🔊 Yes, listen","callback_data":"pronounce:v2"}]]}
        send(token,"sendMessage",payload)
    if replies:
        for part in message_chunks("\n\n".join(dict.fromkeys(replies))): post(part)
    all_correct=all(row is not None and not row["errors"] for _,row in results)
    if all_correct: post("✅ Your entire text looks correct! Well done!")
    for i,(original,row) in enumerate(results,1):
        label=f"Part {i}/{len(results)}"
        if row is None:
            post(label+" — I could not complete this part. Please resend it separately.\n\n"+safe_text(original,1000))
            continue
        corrected=safe_text(row["corrected"],len(row["corrected"]))
        notes,topics=passage_notes(row)
        header=label+(" — Suggested correction:" if row["errors"] else " — Correct!")
        body=header+"\n\n"+corrected
        if notes: body+="\n\nWhy:\n"+"\n".join(notes)
        if topics: body+="\n\nLearn more:\n"+"\n".join(CATALOG[t][0]+": "+CATALOG[t][1] for t in topics)
        targets=[" ".join(t.split()) for t in passage_parts(corrected,480) if t.strip()]
        chunks=list(message_chunks(body))
        for j,chunk in enumerate(chunks):
            if j==len(chunks)-1 and len(targets)==1 and len(chunk)+len(targets[0])<3800:
                post(chunk,targets[0])
                targets=[]
            else: post(chunk)
        for target in targets: post("Listening practice — "+label,target)
    return "passage" if all(row is not None for _,row in results) else "partial_passage"

def handle_update(update, group_id, token, infer=analyze, send=telegram, review=None):
    message=update.get("message", {})
    if not isinstance(message,dict) or not eligible(message,group_id):
        return "ignored"
    text=message["text"].strip()
    if text.startswith("/"):
        command, _, arg=text.partition(" ")
        command, sep, target=command.lower().partition("@")
        if sep and target!="techverseenglishbot": return "ignored"
        reply=("Reply to a voice note with /retry to analyze it again." if command=="/retry" else command_reply(command,arg))
        if reply:
            send(token,"sendMessage",{"chat_id":group_id,"text":reply,"reply_parameters":{"message_id":message["message_id"]},"link_preview_options":{"is_disabled":True}})
            return "command"
        return "ignored"
    if is_long_text(text):
        return handle_passage(message,group_id,token,send,review)
    try:
        raw=guard_language(text,infer(text))
    except Exception as exc:
        print("text_inference_failed:"+type(exc).__name__)
        raw="{}"
    decision=decide(raw)
    chat_reply=conversation(raw)
    spoken=""
    if decision.action == "allow":
        try: correct=json.loads(raw).get("category")=="correct"
        except (ValueError,AttributeError,TypeError): correct=False
        if correct:
            reply="✅ That's correct! Well done!"+("\n\n"+chat_reply if chat_reply else "")
            spoken=text
        else:
            reply=chat_reply or "I couldn't fully understand that. Could you tell me more?"
    elif decision.action == "clarify":
        reply=chat_reply or "Could you rephrase that in English?"
    else:
        reply=(chat_reply+"\n\n" if chat_reply else "")+lesson(raw,decision)
        if decision.action in ("correct","warn"): spoken=decision.correction
    payload={"chat_id":group_id,"text":reply[:3000],
        "reply_parameters":{"message_id":message["message_id"],"allow_sending_without_reply":True},
        "link_preview_options":{"is_disabled":True}}
    target=" ".join(safe_text(spoken,2000).split())
    if target and len(target)<=500 and not foreign_evidence(target):
        payload["text"]+="\n\n🔊 Pronunciation: "+target+"\nWould you like to hear the pronunciation?"
        payload["reply_markup"]={"inline_keyboard":[[{"text":"🔊 Yes, listen","callback_data":"pronounce:v2"}]]}
    send(token,"sendMessage",payload)
    return decision.action

def voice_notice(token,group_id,message,text,send=telegram):
    return send(token,"sendMessage",{"chat_id":group_id,"text":text,"reply_parameters":{"message_id":message["message_id"],"allow_sending_without_reply":True},"link_preview_options":{"is_disabled":True}})

def voice_candidate(message,group_id):
    if not isinstance(message,dict): return False
    chat=message.get("chat",{})
    sender=message.get("from",{})
    return bool(group_id and chat.get("id")==group_id and chat.get("type") in ("group","supergroup") and sender and not sender.get("is_bot",False) and isinstance(message.get("voice"),dict))

def retry_target(message,group_id):
    if not eligible(message,group_id): return None
    command=message["text"].strip().lower()
    if command not in ("/retry","/retry@techverseenglishbot"): return None
    original=message.get("reply_to_message")
    return original if voice_candidate(original,group_id) else None

def pronunciation_target(callback,group_id):
    if not isinstance(callback,dict) or callback.get("data") not in ("pronounce:v1","pronounce:v2"): return ""
    actor=callback.get("from",{})
    message=callback.get("message",{})
    chat=message.get("chat",{})
    author=message.get("from",{})
    if not group_id or chat.get("id")!=group_id or chat.get("type") not in ("group","supergroup"): return ""
    if not actor.get("id") or actor.get("is_bot") or not author.get("is_bot") or str(author.get("username","")).lower()!="techverseenglishbot": return ""
    text=message.get("text","")
    if not isinstance(text,str): return ""
    before,sep,tail=text.rpartition("\n\n🔊 Pronunciation: ")
    target,sep2,end=tail.partition("\nWould you like to hear the pronunciation?")
    return target if sep and sep2 and not end and 0<len(target)<=500 and "\n" not in target else ""

def handle_pronunciation(callback,group_id,token,send=None,play=None,quota=None):
    send=send or telegram
    play=play or send_voice
    quota=quota or consume_quota
    target=pronunciation_target(callback,group_id)
    if not target: return "ignored"
    cid=callback["id"]
    if callback.get("data")=="pronounce:v1" or foreign_evidence(target):
        send(token,"answerCallbackQuery",{"callback_query_id":cid,"text":"This pronunciation offer is outdated or not English. Please resend the sentence for a new English version.","show_alert":True})
        return "foreign"
    if not quota("playback",((60,2),(86400,30))):
        send(token,"answerCallbackQuery",{"callback_query_id":cid,"text":"Listening limit reached. Try again later.","show_alert":True})
        return "limited"
    send(token,"answerCallbackQuery",{"callback_query_id":cid,"text":"Preparing pronunciation…"})
    try:
        play(token,group_id,callback["message"]["message_id"],target)
    except Exception:
        voice_notice(token,group_id,callback["message"],"I couldn't generate the audio. Please try again.",send)
        return "error"
    return "played"

def response(status):
    return {"statusCode":status,"body":""}

def handler(event, context):
    try:
        cfg=config()
        token=cfg["TELEGRAM_BOT_TOKEN"]
        if "requestContext" not in event:
            if event.get("operation") == "delivery_selftest":
                if expired(): return {"status":"expired"}
                group_id=int(cfg.get("GROUP_ID",0))
                if not group_id: return {"status":"group_missing"}
                sample="I like learning English every day."
                sent=telegram(token,"sendMessage",{"chat_id":group_id,"text":"TechVerse Tutor — deployment test.\n"+sample+"\nListen and repeat!","link_preview_options":{"is_disabled":True}})
                voice_id=send_voice(token,group_id,sent["message_id"],sample)
                return {"status":"delivered","text_message_id":sent["message_id"],"voice_message_id":voice_id}
            if event.get("operation") == "passage_worker":
                if expired(): return {"status":"expired"}
                group_id=int(cfg.get("GROUP_ID",0))
                message=event.get("message",{})
                if not eligible(message,group_id) or not is_long_text(message["text"]): return {"status":"ignored"}
                try:
                    return {"status":handle_passage(message,group_id,token,telegram)}
                except Exception as exc:
                    print("passage_worker_failed:"+type(exc).__name__)
                    try: voice_notice(token,group_id,message,"I could not finish reviewing your text. Please try again in smaller sections.")
                    except Exception: pass
                    return {"status":"error"}
            if event.get("operation") == "voice_worker":
                if expired(): return {"status":"expired"}
                group_id=int(cfg.get("GROUP_ID",0))
                message=event.get("message",{})
                if not voice_eligible(message,group_id): return {"status":"ignored"}
                try:
                    outcome=process_voice(token,group_id,message,telegram)
                    print("voice_worker_"+outcome)
                    return {"status":outcome}
                except Exception as exc:
                    print("voice_worker_failed:"+type(exc).__name__)
                    try: voice_notice(token,group_id,message,"I could not process this recording. Please try again later.")
                    except Exception: print("voice_error_notice_failed")
                    return {"status":"voice_error"}
            if event.get("operation") == "discover":
                info=telegram(token,"getWebhookInfo",{})
                if info.get("url"):
                    return {"status":"existing_webhook"}
                updates=telegram(token,"getUpdates",{"timeout":0,"limit":100})
                chats={}
                for update in updates:
                    for key in ("message","my_chat_member"):
                        chat=update.get(key,{}).get("chat",{})
                        if chat.get("type") in ("group","supergroup"):
                            chats[chat["id"]]={"id":chat["id"],"title":chat.get("title","")}
                return {"groups":list(chats.values())}
            if event.get("operation") == "activate":
                group_id=int(cfg["GROUP_ID"])
                chat=telegram(token,"getChat",{"chat_id":group_id})
                me=telegram(token,"getMe",{})
                member=telegram(token,"getChatMember",{"chat_id":group_id,"user_id":me["id"]})
                if chat.get("type") not in ("group","supergroup") or member.get("status")!="administrator":
                    return {"status":"invalid_group"}
                url=event["url"]
                if not url.startswith("https://") or not url.rstrip("/").endswith(".lambda-url.us-east-1.on.aws"):
                    return {"status":"invalid_url"}
                current=telegram(token,"getWebhookInfo",{})
                if current.get("url") and current["url"]!=url:
                    return {"status":"existing_webhook"}
                telegram(token,"setWebhook",{"url":url,"secret_token":cfg["WEBHOOK_SECRET"],"allowed_updates":["message","callback_query"],"max_connections":2})
                return {"status":"active","can_delete":member.get("can_delete_messages",False)}
            return {"status":"ignored"}
        headers={k.lower():v for k,v in (event.get("headers") or {}).items()}
        expected=cfg["WEBHOOK_SECRET"]
        if not hmac.compare_digest(headers.get("x-telegram-bot-api-secret-token",""),expected):
            return response(403)
        if expired():
            return response(200)
        body=event.get("body","")
        if len(body)>30000:
            return response(200)
        if event.get("isBase64Encoded"):
            body=base64.b64decode(body).decode()
        update=json.loads(body)
        group_id=int(cfg.get("GROUP_ID",0))
        if not group_id:
            return response(200)
        callback=update.get("callback_query")
        if callback is not None and not pronunciation_target(callback,group_id): return response(200)
        message=update.get("message",{})
        retry=retry_target(message,group_id)
        is_voice=voice_candidate(message,group_id) or retry is not None
        if callback is None and not is_voice and not eligible(message,group_id):
            return response(200)
        # Atomic deduplication of update IDs, no message content retained.
        import boto3
        from botocore.exceptions import ClientError
        try:
            boto3.client("dynamodb").put_item(TableName=os.environ["DEDUP_TABLE"],
                Item={"id":{"S":str(update["update_id"])},"expires":{"N":str(int(datetime.datetime.now(datetime.timezone.utc).timestamp())+86400)}},
                ConditionExpression="attribute_not_exists(id)")
        except ClientError as exc:
            if exc.response["Error"]["Code"]=="ConditionalCheckFailedException":
                return response(200)
            raise
        if callback is not None:
            handle_pronunciation(callback,group_id,token)
            return response(200)
        if is_voice:
            if retry is not None: message=retry
            if not voice_eligible(message,group_id):
                if consume_quota("notice",((60,5),(86400,60))):
                    voice_notice(token,group_id,message,"Please send a voice note up to 30 seconds and 2 MB.")
                return response(200)
            if os.environ.get("VOICE_INPUT_ENABLED","false").lower()!="true":
                telegram(token,"sendMessage",{"chat_id":group_id,"text":"Voice recognition is temporarily unavailable. You can still practice listening with /listen followed by an English sentence.","reply_parameters":{"message_id":message["message_id"]}})
                return response(200)
            if not consume_quota("voice",((60,5),(86400,120))):
                if consume_quota("notice",((60,5),(86400,60))):
                    voice_notice(token,group_id,message,"Voice practice limit reached. Please try again in a minute or tomorrow if the daily limit is reached.")
                return response(200)
            minimal={"chat":{"id":group_id,"type":message["chat"]["type"]},"from":{"is_bot":False},"message_id":message["message_id"],"voice":{k:message["voice"][k] for k in ("file_id","duration","file_size") if k in message["voice"]}}
            try:
                queued=boto3.client("lambda").invoke(FunctionName=os.environ["AWS_LAMBDA_FUNCTION_NAME"],InvocationType="Event",Payload=json.dumps({"operation":"voice_worker","message":minimal}).encode())
                if queued.get("StatusCode")!=202: raise RuntimeError("queue rejected")
            except Exception:
                print("voice_enqueue_failed")
                voice_notice(token,group_id,message,"I could not start processing your audio. Please try again.")
                return response(200)
            print("voice_queued")
            voice_notice(token,group_id,message,"🎧 I received your voice note. I am listening for your intended English sentence.")
        else:
            text=message['text'].strip()
            cmd, _, arg=text.partition(' ')
            name, sep, target=cmd.lower().partition('@')
            if name=='/listen' and (not sep or target=='techverseenglishbot'):
                if consume_quota('playback',((60,2),(86400,30))):
                    spoken=arg.strip()[:500]
                    if spoken:
                        raw=analyze(spoken)
                        decision=decide(raw)
                        try: category=json.loads(raw).get("category")
                        except (ValueError,AttributeError,TypeError): category=None
                        target_text=decision.correction if decision.action in ("correct","warn") else spoken if category=="correct" else ""
                        if target_text and not foreign_evidence(target_text):
                            if target_text!=spoken: voice_notice(token,group_id,message,"English version: "+target_text)
                            send_voice(token,group_id,message["message_id"],target_text)
                        else: voice_notice(token,group_id,message,"I could not verify an English version. Please try again.")
            else:
                if not text.startswith('/') and is_long_text(text):
                    if not consume_quota("passage",((60,2),(86400,20))):
                        if consume_quota("notice",((60,5),(86400,60))):
                            voice_notice(token,group_id,message,"Long-text review limit reached. Please try again later.")
                        return response(200)
                    minimal={"chat":{"id":group_id,"type":message["chat"]["type"]},"from":{"is_bot":False},"message_id":message["message_id"],"text":text}
                    try:
                        queued=boto3.client("lambda").invoke(FunctionName=os.environ["AWS_LAMBDA_FUNCTION_NAME"],InvocationType="Event",Payload=json.dumps({"operation":"passage_worker","message":minimal}).encode())
                        if queued.get("StatusCode")!=202: raise RuntimeError("queue rejected")
                        voice_notice(token,group_id,message,"📝 I received your text. I'll review every section and answer your questions.")
                    except Exception as exc:
                        print("passage_enqueue_failed:"+type(exc).__name__)
                        voice_notice(token,group_id,message,"I couldn't start reviewing your text. Please try again.")
                elif text.startswith('/') or consume_quota():
                    handle_update(update,group_id,token)
                elif consume_quota('notice',((60,5),(86400,60))):
                    voice_notice(token,group_id,message,'Text practice limit reached. Please try again later.')
        return response(200)
    except Exception as exc:
        print("handler_failed:"+type(exc).__name__)
        # Never expose raw payload, token, or provider exception.
        return response(200) if "requestContext" in event else {"status":"error"}


def consume_quota(scope="text", limits=((60,20),(86400,500))):
    """Bound paid inference calls to 20/minute and 500/day for the entire group."""
    import boto3
    from botocore.exceptions import ClientError
    now=int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    db=boto3.client("dynamodb")
    for period,limit in limits:
        try:
            db.update_item(TableName=os.environ["DEDUP_TABLE"],
                Key={"id":{"S":f"quota:{scope}:{period}:{now//period}"}},
                UpdateExpression="SET expires = :expiry ADD #hits :one",
                ConditionExpression="attribute_not_exists(#hits) OR #hits < :limit",
                ExpressionAttributeNames={"#hits":"hits"},
                ExpressionAttributeValues={":expiry":{"N":str(now+period+86400)},":one":{"N":"1"},":limit":{"N":str(limit)}})
        except ClientError as exc:
            if exc.response["Error"]["Code"]=="ConditionalCheckFailedException":
                return False
            raise
    return True


def expired():
    return datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(os.environ["EXPIRES_AT"])

def voice_eligible(message,group_id):
    if not isinstance(message,dict): return False
    chat=message.get("chat",{})
    sender=message.get("from",{})
    return bool(group_id and chat.get("id")==group_id and chat.get("type") in ("group","supergroup") and sender and not sender.get("is_bot",False) and voice_allowed(message.get("voice")))
