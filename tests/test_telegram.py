import unittest
import json
from src.telegram_runtime import handle_update

class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.update={"update_id":1,"message":{"chat":{"id":-123,"type":"supergroup"},
            "from":{"id":1},"message_id":5,"text":"I goed home."}}
    def send(self,token,method,payload):
        self.calls.append((method,payload))
    def infer(self,text):
        return json.dumps({"category":"english_error","correction":"I went home.","explanation":"Go is irregular."})
    def test_correction(self):
        self.assertEqual(handle_update(self.update,-123,"fake",self.infer,self.send),"correct")
        self.assertEqual(self.calls[0][0],"sendMessage")
        self.assertEqual(self.calls[0][1]["chat_id"],-123)
        self.assertEqual(self.calls[0][1]["reply_parameters"]["message_id"],5)
    def test_foreign_group(self):
        self.assertEqual(handle_update(self.update,-456,"fake",self.infer,self.send),"ignored")
        self.assertEqual(self.calls,[])
    def test_portuguese_warning(self):
        def infer(text):
            return '{"category":"portuguese_only","correction":"Good morning","explanation":""}'
        self.assertEqual(handle_update(self.update,-123,"fake",infer,self.send),"warn")
        self.assertEqual([call[0] for call in self.calls],["sendMessage"])
    def test_correct_english_replies(self):
        self.assertEqual(handle_update(self.update,-123,"fake",lambda t:'{"category":"correct","conversational_reply":"Thank you!"}',self.send),"allow")
        self.assertEqual(self.calls[0][1]["text"],"Thank you!")
    def test_command_ignored(self):
        self.update["message"]["text"]="/unknown"
        self.assertEqual(handle_update(self.update,-123,"fake",self.infer,self.send),"ignored")
        self.assertEqual(self.calls,[])

    def test_help_command(self):
        self.update["message"]["text"]="/help@techverseEnglishBot"
        self.assertEqual(handle_update(self.update,-123,"fake",lambda t:self.fail("no model for commands"),self.send),"command")
        self.assertIn("/learn",self.calls[0][1]["text"])
    def test_learn_command(self):
        self.update["message"]["text"]="/learn past"
        self.assertEqual(handle_update(self.update,-123,"fake",lambda t:self.fail("no model for commands"),self.send),"command")
        self.assertIn("https://learnenglish.britishcouncil.org/",self.calls[0][1]["text"])
    def test_other_bot_command(self):
        self.update["message"]["text"]="/help@otherbot"
        self.assertEqual(handle_update(self.update,-123,"fake",self.infer,self.send),"ignored")
        self.assertEqual(self.calls,[])

    def test_insult_question_replies(self):
        self.update["message"]["text"]="You're an idiot, what do you think about that?"
        raw='{"category":"correct","conversational_reply":"That is an insult. What would you like to discuss?"}'
        handle_update(self.update,-123,"fake",lambda t:raw,self.send)
        self.assertIn("insult",self.calls[0][1]["text"])
    def test_inference_failure_replies(self):
        def fail(text): raise RuntimeError("unavailable")
        handle_update(self.update,-123,"fake",fail,self.send)
        self.assertIn("tell me more",self.calls[0][1]["text"])
