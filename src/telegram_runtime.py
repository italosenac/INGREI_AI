"""Telegram runtime. No message bodies or secrets are logged."""
import base64
import datetime
import hmac
import json
import os
import urllib.request
from .policy import decide, eligible
from .inference import analyze

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
    if text.startswith("/") or not any(c.isalpha() for c in text):
        return "ignored"
    decision=decide(infer(text))
    if decision.action == "allow":
        return "allowed"
    if decision.action == "clarify":
        reply="Could you rephrase that in English?"
    elif decision.action == "warn":
        reply="English only, please. Try: "+decision.correction
    else:
        reply="Suggested correction: "+decision.correction
        if decision.explanation:
            reply+="\nWhy: "+decision.explanation
    send(token,"sendMessage",{"chat_id":group_id,"text":reply[:3500],
        "reply_parameters":{"message_id":message["message_id"],"allow_sending_without_reply":False},
        "link_preview_options":{"is_disabled":True}})
    return decision.action

def response(status):
    return {"statusCode":status,"body":""}

def handler(event, context):
    try:
        cfg=config()
        token=cfg["TELEGRAM_BOT_TOKEN"]
        if "requestContext" not in event:
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
        if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(os.environ["EXPIRES_AT"]):
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
        if not eligible(message,group_id):
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
        if not consume_quota():
            return response(200)
        handle_update(update,group_id,token)
        return response(200)
    except Exception:
        # Never expose raw payload, token, or provider exception.
        return response(200) if "requestContext" in event else {"status":"error"}


def consume_quota():
    """Bound paid inference calls to 20/minute and 500/day for the entire group."""
    import boto3
    from botocore.exceptions import ClientError
    now=int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    db=boto3.client("dynamodb")
    for period,limit in ((60,20),(86400,500)):
        try:
            db.update_item(TableName=os.environ["DEDUP_TABLE"],
                Key={"id":{"S":f"quota:{period}:{now//period}"}},
                UpdateExpression="SET expires = :expiry ADD #hits :one",
                ConditionExpression="attribute_not_exists(#hits) OR #hits < :limit",
                ExpressionAttributeNames={"#hits":"hits"},
                ExpressionAttributeValues={":expiry":{"N":str(now+period+86400)},":one":{"N":"1"},":limit":{"N":str(limit)}})
        except ClientError as exc:
            if exc.response["Error"]["Code"]=="ConditionalCheckFailedException":
                return False
            raise
    return True
