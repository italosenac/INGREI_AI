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
    def test_correct_english_silent(self):
        self.assertEqual(handle_update(self.update,-123,"fake",lambda t:'{"category":"correct"}',self.send),"allowed")
        self.assertEqual(self.calls,[])
    def test_command_ignored(self):
        self.update["message"]["text"]="/start"
        self.assertEqual(handle_update(self.update,-123,"fake",self.infer,self.send),"ignored")
        self.assertEqual(self.calls,[])
