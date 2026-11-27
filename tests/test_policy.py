import unittest
import json
from src.policy import decide, eligible
from src.inference import normalize

class PolicyTests(unittest.TestCase):
    def test_categories(self):
        for category, expected in [
            ("correct","allow"),("ambiguous","allow"),("nonlinguistic","allow"),
            ("english_error","correct"),("mixed","correct"),("phonetic","correct"),
            ("unclear","clarify"),("portuguese_only","warn"),("unknown","allow")]:
            with self.subTest(category=category):
                self.assertEqual(decide(json.dumps({"category":category,"correction":"I like English.","explanation":"Example"})).action,expected)
    def test_no_automatic_deletion(self):
        self.assertEqual(decide('{"category":"portuguese_only","correction":"Hello"}',True).action,"review")
    def test_invalid(self):
        for raw in ["", "[]", "null", '{"category":[]}', '{"category":"mixed","correction":3}']:
            self.assertEqual(decide(raw).action,"allow")
    def test_group(self):
        msg={"chat":{"id":-123,"type":"group"},"from":{"id":1},"text":"Hello"}
        self.assertTrue(eligible(msg,-123))
        self.assertFalse(eligible(msg,-456))
        msg["from"]["is_bot"]=True
        self.assertFalse(eligible(msg,-123))
    def test_fences(self):
        self.assertEqual(normalize('```json\n{}\n```'),"{}")

    def test_tone_is_not_grammar(self):
        self.assertEqual(decide('{"category":"english_error","correction":"What are you talking about?","explanation":"The phrase is rude and informal."}').action,"allow")
        self.assertEqual(decide('{"category":"english_error","correction":"You are rude.","explanation":"Missing verb: use are with you."}').action,"correct")

if __name__=="__main__":
    unittest.main()
