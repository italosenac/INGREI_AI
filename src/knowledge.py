"""Curated teaching links; no model-generated URLs are trusted."""
import re
CATALOG = {
  "past": [
    "Past simple and irregular verbs",
    "https://learnenglish.britishcouncil.org/free-resources/grammar/english-grammar-reference/irregular-verbs"
  ],
  "present": [
    "Present simple",
    "https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2/present-simple"
  ],
  "be": [
    "Verb to be",
    "https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2/present-simple-be"
  ],
  "prepositions": [
    "Adjectives and prepositions",
    "https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2/adjectives-prepositions"
  ],
  "articles": [
    "Beginner grammar: articles",
    "https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2"
  ],
  "countability": [
    "Countable and uncountable nouns",
    "https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2/nouns-countable-uncountable"
  ],
  "questions": [
    "Question forms",
    "https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2/question-forms"
  ],
  "verb_patterns": [
    "Verb patterns",
    "https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2/verbs-followed-ing-or-infinitive"
  ],
  "perfect": [
    "Present perfect",
    "https://learnenglish.britishcouncil.org/free-resources/grammar/b1-b2/present-perfect"
  ],
  "word_order": [
    "Word order",
    "https://dictionary.cambridge.org/grammar/british-grammar/word-order-structures"
  ],
  "vocabulary": [
    "Cambridge Learner's Dictionary",
    "https://dictionary.cambridge.org/dictionary/learner-english/"
  ],
  "listening": [
    "A1 listening practice",
    "https://learnenglish.britishcouncil.org/free-resources/listening/a1"
  ],
  "general": [
    "A1–A2 grammar and exercises",
    "https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2"
  ]
}
TOPICS = ", ".join(CATALOG)
def safe_text(value, limit):
    if not isinstance(value,str):
        return ""
    return re.sub(r"(?i)(?:https?://|www\\.|t\\.me/)[^\\s]+", "", value).strip()[:limit]
def lesson(raw, decision):
    import json
    try:
        data=json.loads(raw)
        if not isinstance(data,dict): data={}
    except (ValueError,TypeError):
        data={}
    topic=data.get("topic")
    if not isinstance(topic,str) or topic not in CATALOG:
        topic="general"
    title,url=CATALOG[topic]
    result="Suggested correction: "+safe_text(decision.correction,1200)
    if decision.action=="warn":
        result="English only, please. Try: "+safe_text(decision.correction,1200)
    why=safe_text(decision.explanation,500)
    if why: result+="\n\nWhy: "+why
    example=safe_text(data.get("example"),200)
    if example: result+="\n\nExample: "+example
    practice=safe_text(data.get("practice"),180)
    if practice: result+="\n\nTry it: "+practice
    return result+"\n\nLearn more — "+title+":\n"+url
