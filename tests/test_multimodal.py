import json
import unittest
from src.knowledge import lesson, CATALOG
from src.policy import decide
from src.speech import voice_allowed, voice_feedback
from src.telegram_runtime import voice_eligible, handle_update

class MultimodalTests(unittest.TestCase):
    def test_topic_link(self):
        raw=json.dumps({"category":"english_error","correction":"I went home.","explanation":"Past tense.","topic":"past","example":"She went home.","practice":"I ___ home yesterday."})
        result=lesson(raw,decide(raw))
        self.assertIn(CATALOG["past"][1],result)
        self.assertIn("Try it:",result)
        self.assertIn("Example:",result)
    def test_untrusted_links(self):
        raw=json.dumps({"category":"english_error","correction":"I went home.","explanation":"Visit https://evil.example","topic":"https://evil.example"})
        result=lesson(raw,decide(raw))
        self.assertNotIn("evil.example",result)
        self.assertIn(CATALOG["general"][1],result)
    def test_voice_limits(self):
        voice={"file_id":"abc","duration":10,"file_size":100}
        self.assertTrue(voice_allowed(voice))
        self.assertFalse(voice_allowed(dict(voice,duration=31)))
        self.assertFalse(voice_allowed(dict(voice,file_size=2000001)))
    def test_voice_group_isolation(self):
        msg={"chat":{"id":-123,"type":"supergroup"},"from":{"id":1},"voice":{"file_id":"abc","duration":10}}
        self.assertTrue(voice_eligible(msg,-123))
        self.assertFalse(voice_eligible(msg,-124))
        msg["from"]["is_bot"]=True
        self.assertFalse(voice_eligible(msg,-123))
    def test_voice_low_confidence(self):
        reply,spoken=voice_feedback("hello",0.2,lambda t:self.fail("should not infer"))
        self.assertFalse(spoken)
        self.assertIn("try again",reply)
    def test_voice_correction(self):
        reply,spoken=voice_feedback("I goed home",0.9,lambda t:'{"category":"english_error","correction":"I went home.","topic":"past"}')
        self.assertEqual(spoken,"I went home.")
        self.assertIn(CATALOG["past"][1],reply)
        self.assertIn("not a pronunciation score",reply)
    def test_no_false_praise(self):
        reply,spoken=voice_feedback("I goed home",0.9,lambda t:"{}")
        self.assertFalse(spoken)
        self.assertIn("couldn't assess",reply)
    def test_correct_voice(self):
        reply,spoken=voice_feedback("I like English",0.9,lambda t:'{"category":"correct"}')
        self.assertEqual(spoken,"I like English")
        self.assertIn("transcribed sentence looks correct",reply)
