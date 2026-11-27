"""Telegram runtime. No message bodies or secrets are logged."""
import base64
import datetime
import hmac
import json
import os
import urllib.request
from .policy import decide, eligible
from .inference import analyze
from .knowledge import lesson, command_reply
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

def handle_update(update, group_id, token, infer=analyze, send=telegram):
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
    if not any(c.isalpha() for c in text):
        return "ignored"
    raw=infer(text)
    decision=decide(raw)
    if decision.action == "allow":
        return "allowed"
    if decision.action == "clarify":
        reply="Could you rephrase that in English?"
    elif decision.action == "warn":
        reply=lesson(raw,decision)
    else:
        reply=lesson(raw,decision)
    send(token,"sendMessage",{"chat_id":group_id,"text":reply[:3500],
        "reply_parameters":{"message_id":message["message_id"],"allow_sending_without_reply":False},
        "link_preview_options":{"is_disabled":True}})
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
                telegram(token,"setWebhook",{"url":url,"secret_token":cfg["WEBHOOK_SECRET"],"allowed_updates":["message"],"max_connections":2})
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
        message=update.get("message",{})
        retry=retry_target(message,group_id)
        is_voice=voice_candidate(message,group_id) or retry is not None
        if not is_voice and not eligible(message,group_id):
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
                    if spoken: send_voice(token,group_id,message['message_id'],spoken)
            else:
                if text.startswith('/') or consume_quota():
                    handle_update(update,group_id,token)
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
