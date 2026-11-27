"""Pure decision policy. Model scores are not calibrated probabilities."""
from dataclasses import dataclass
import json

@dataclass(frozen=True)
class Decision:
    action: str
    correction: str = ""
    explanation: str = ""

def decide(raw: str, deletion_enabled: bool = False) -> Decision:
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return Decision("allow")
        category = data.get("category")
        correction = data.get("correction", "")
        explanation = data.get("explanation", "")
        if not isinstance(correction, str) or not isinstance(explanation, str):
            return Decision("allow")
        if len(correction) > 2000 or len(explanation) > 1000:
            return Decision("allow")
        if category in ("correct", "ambiguous", "nonlinguistic"):
            return Decision("allow")
        if category in ("english_error", "mixed", "phonetic") and correction.strip():
            return Decision("correct", correction.strip(), explanation.strip())
        if category == "unclear":
            return Decision("clarify")
        if category == "portuguese_only" and correction.strip():
            return Decision("review" if deletion_enabled else "warn", correction.strip(), explanation.strip())
    except (ValueError, TypeError, RecursionError):
        pass
    return Decision("allow")

def eligible(message: dict, group_id: int) -> bool:
    chat = message.get("chat", {})
    sender = message.get("from", {})
    text = message.get("text")
    return (chat.get("id") == group_id and chat.get("type") in ("group", "supergroup")
            and bool(sender) and not sender.get("is_bot", False)
            and isinstance(text, str) and 0 < len(text.strip()) <= 2000)
