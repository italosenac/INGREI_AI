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
  "place": ["Prepositions of place", "https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2/prepositions-place"],
  "time": ["Prepositions of time", "https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2-grammar/prepositions-of-time-at-in-on"],
  "comparatives": ["Comparative adjectives", "https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2/comparative-adjectives"],
  "perfect_continuous": ["Present perfect simple and continuous", "https://learnenglish.britishcouncil.org/free-resources/grammar/b1-b2/present-perfect-simple-continuous"],
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
  "greetings": ["Meeting new people — A1 speaking", "https://learnenglish.britishcouncil.org/free-resources/speaking/a1/meeting-new-people"],
  "pronunciation": ["English sounds and phonemic chart", "https://learnenglish.britishcouncil.org/apps/learnenglish-sounds-right"],
  "conditionals": ["Intermediate grammar: conditionals", "https://learnenglish.britishcouncil.org/free-resources/grammar/b1-b2"],
  "modals": ["Modal verbs", "https://learnenglish.britishcouncil.org/free-resources/grammar/english-grammar-reference/verbs"],
  "general": [
    "A1–A2 grammar and exercises",
    "https://learnenglish.britishcouncil.org/free-resources/grammar/a1-a2"
  ]
}
TOPICS = ", ".join(CATALOG)
def safe_text(value, limit):
    if not isinstance(value,str):
        return ""
    return re.sub(r"(?i)(?:[a-z][a-z0-9+.-]*://|www\.|t\.me/|(?:[a-z0-9-]+\.)+(?:com|org|net|io|edu|gov|co|me|info|xyz|example)\b)[^\s]*", "", value).strip()[:limit]
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

def command_reply(command, argument=""):
    """Free deterministic study commands; no model or external fetch."""
    if command in ("/start","/help"):
        return ("TechVerse English Tutor\n"
                "Write in English, even if you make mistakes. I reply to correct sentences too, and offer corrections and practice when needed.\n"
                "/learn — browse lesson topics\n"
                "/learn past — open a specific lesson\n"
                "/listen I love English. — hear an English sentence\n"
                "/rules — group rules\n"
                "/retry — reply to a voice note to analyze it again\n"
                "Send a voice note up to 30 seconds when voice recognition is enabled.")
    if command=="/rules":
        return ("English only, please. Mistakes, mixed phrases and attempts are welcome! "
                "I suggest corrections; if I am unsure, I ask you to rephrase. "
                "Do not send passwords, personal information or private recordings.")
    if command=="/learn":
        topic=argument.strip().lower().replace(" ","_")
        if topic in CATALOG:
            title,url=CATALOG[topic]
            return "Learn more — "+title+":\n"+url
        return "Study topics: "+TOPICS+"\nUse /learn past or another topic from the list."
    return ""

def conversation(raw):
    import json
    try:
        data=json.loads(raw)
        return safe_text(data.get("conversational_reply"),500)
    except (ValueError,TypeError,AttributeError):
        return ""

