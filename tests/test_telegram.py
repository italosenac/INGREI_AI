import unittest
import json
from src.telegram_runtime import handle_update, handle_pronunciation, pronunciation_target

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
        self.assertIn("🔊 Pronunciation: I went home.\n",self.calls[0][1]["text"])
        self.assertEqual(self.calls[0][1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"],"pronounce:v1")
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
        self.assertIn("That's correct!",self.calls[0][1]["text"])
        self.assertIn("Thank you!",self.calls[0][1]["text"])
        self.assertIn("Would you like to hear the pronunciation?",self.calls[0][1]["text"])
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

    def test_pronunciation_callback(self):
        self.update["message"]["text"]="You're an amazing person."
        handle_update(self.update,-123,"fake",lambda t:'{"category":"correct","conversational_reply":"Thanks!"}',self.send)
        payload=self.calls[0][1]
        cb={"id":"cb1","data":"pronounce:v1","from":{"id":7},"message":{"chat":{"id":-123,"type":"supergroup"},"from":{"is_bot":True,"username":"techverseEnglishBot"},"message_id":8,"text":payload["text"]}}
        self.assertEqual(pronunciation_target(cb,-123),"You're an amazing person.")
        played=[]
        self.assertEqual(handle_pronunciation(cb,-123,"fake",self.send,lambda *a:played.append(a),lambda *a:True),"played")
        self.assertEqual(played,[("fake",-123,8,"You're an amazing person.")])
        self.assertEqual(self.calls[-1][0],"answerCallbackQuery")
        self.assertEqual(handle_pronunciation(cb,-123,"fake",self.send,lambda *a:self.fail("quota"),lambda *a:False),"limited")
        self.assertEqual(handle_pronunciation(cb,-999,"fake",self.send,lambda *a:self.fail("foreign group"),lambda *a:True),"ignored")
        cb["message"]["from"]["is_bot"]=False
        self.assertEqual(pronunciation_target(cb,-123),"")
    def test_no_audio_offer_for_unclear(self):
        handle_update(self.update,-123,"fake",lambda t:'{"category":"unclear"}',self.send)
        self.assertNotIn("reply_markup",self.calls[0][1])
    def test_no_false_praise_for_invalid_model(self):
        handle_update(self.update,-123,"fake",lambda t:'{}',self.send)
        self.assertNotIn("That's correct!",self.calls[0][1]["text"])
        self.assertNotIn("reply_markup",self.calls[0][1])
