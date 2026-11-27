import json
import unittest
from src.knowledge import lesson, CATALOG
from src.policy import decide
from src.speech import voice_allowed, voice_feedback, transcribe_bytes
from unittest.mock import patch
import io
import os
from src.telegram_runtime import voice_eligible, handle_update, voice_candidate, voice_notice

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
        reply,spoken=voice_feedback("hello",0.2,lambda t: '{"category":"correct"}')
        self.assertFalse(spoken)
        self.assertIn("My best guess",reply)
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

    def test_whisper_invocation(self):
        class Client:
            def invoke(self, **kwargs):
                self.kwargs=kwargs
                return {"Payload":io.BytesIO(b'{"status":"complete","text":"I like English."}')}
        client=Client()
        with patch.dict(os.environ,{"WHISPER_FUNCTION":"test-worker"}):
            self.assertEqual(transcribe_bytes(b"OggS",client),("I like English.",None))
        self.assertEqual(client.kwargs["FunctionName"],"test-worker")
        self.assertEqual(json.loads(client.kwargs["Payload"])["audio"],"T2dnUw==")
    def test_whisper_uncertainty(self):
        class Client:
            def invoke(self, **kwargs):
                return {"Payload":io.BytesIO(b'{"status":"uncertain","text":""}')}
        with patch.dict(os.environ,{"WHISPER_FUNCTION":"test-worker"}):
            self.assertEqual(transcribe_bytes(b"OggS",Client()),("",None))
    def test_whisper_failure(self):
        class Client:
            def invoke(self, **kwargs):
                return {"FunctionError":"Unhandled","Payload":io.BytesIO(b'{}')}
        with patch.dict(os.environ,{"WHISPER_FUNCTION":"test-worker"}):
            with self.assertRaises(RuntimeError):
                transcribe_bytes(b"OggS",Client())
    def test_whisper_size(self):
        with self.assertRaises(ValueError):
            transcribe_bytes(b"")
    def test_bare_link_removed(self):
        raw=json.dumps({"category":"english_error","correction":"I like English.","explanation":"Visit evil.example or ftp://bad.example/file","topic":"past"})
        result=lesson(raw,decide(raw))
        self.assertNotIn("evil.example",result)
        self.assertNotIn("bad.example",result)

    def test_ambiguous_voice_alternatives(self):
        raw=json.dumps({"category":"unclear","possible_meaning":"Thank you very much, my friend.","alternate_meaning":"I like you very much, my friend."})
        reply,spoken=voice_feedback("Hi que o very much my friend",None,lambda t:raw)
        self.assertIn("Possible meanings (not confirmed)",reply)
        self.assertIn("Thank you very much, my friend.",reply)
        self.assertIn("Which meaning did you intend?",reply)
        self.assertFalse(spoken)
    def test_empty_transcript_has_help(self):
        reply,spoken=voice_feedback("",None,lambda t:self.fail("no inference"))
        self.assertIn("Speaking practice:",reply)
        self.assertFalse(spoken)
    def test_oversize_voice_can_receive_notice(self):
        message={"chat":{"id":-123,"type":"supergroup"},"from":{"id":1},"message_id":5,"voice":{"file_id":"abc","duration":60}}
        self.assertTrue(voice_candidate(message,-123))
        self.assertFalse(voice_eligible(message,-123))
        self.assertFalse(voice_candidate(message,-999))
        calls=[]
        voice_notice("fake",-123,message,"Please shorten the recording.",lambda t,m,p:calls.append(p))
        self.assertTrue(calls[0]["reply_parameters"]["allow_sending_without_reply"])
    def test_uncertain_hypotheses_preserved(self):
        class Client:
            def invoke(self, **kwargs):
                return {"Payload":io.BytesIO(b'{"status":"uncertain","text":"que o","alternate":"thank you"}')}
        with patch.dict(os.environ,{"WHISPER_FUNCTION":"test-worker"}):
            self.assertEqual(transcribe_bytes(b"OggS",Client()),("que o | thank you",0.4))
    def test_uncertain_correction_is_tentative(self):
        reply,spoken=voice_feedback("ai laik inglish",0.4,lambda t:'{"category":"phonetic","correction":"I like English.","topic":"pronunciation"}')
        self.assertIn("My best guess (please confirm)",reply)
        self.assertEqual(spoken,"I like English.")
