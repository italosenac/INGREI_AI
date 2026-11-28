import unittest
import json
from src.telegram_runtime import handle_update, handle_pronunciation, pronunciation_target
from src.knowledge import passage_parts, passage_batches, message_chunks
from src.inference import review_passage, language_evidence, guard_language, analyze, foreign_evidence

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
        self.assertEqual(self.calls[0][1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"],"pronounce:v2")
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
        cb={"id":"cb1","data":"pronounce:v2","from":{"id":7},"message":{"chat":{"id":-123,"type":"supergroup"},"from":{"is_bot":True,"username":"techverseEnglishBot"},"message_id":8,"text":payload["text"]}}
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

    def test_long_passage_full_delivery(self):
        p1="I goed home yesterday. "*15
        p2="She don't like coffee. "*12
        p3="What do you think? "*10
        self.update["message"]["text"]="\n".join([p1,p2,p3])
        def review(parts):
            rows=[]
            for i,p in enumerate(parts,1):
                corrected=p.replace("goed","went").replace("don't","doesn't")
                errors=[] if corrected==p else [{"original":"goed" if "goed" in p else "don't","corrected":"went" if "goed" in p else "doesn't","why":"Use the correct verb form.","topic":"past"}]
                rows.append({"id":i,"corrected":corrected,"errors":errors})
            return {"paragraphs":rows,"conversational_reply":"Keep practicing!"}
        self.assertEqual(handle_update(self.update,-123,"fake",lambda t:self.fail("short model"),self.send,review),"passage")
        texts=[p["text"] for m,p in self.calls]
        self.assertTrue(any("Keep practicing!" in t for t in texts))
        self.assertTrue(any("went home" in t for t in texts))
        self.assertTrue(any("doesn't like" in t for t in texts))
        self.assertTrue(any("What do you think?" in t for t in texts))
        self.assertTrue(any(p.get("reply_markup") for m,p in self.calls))
        self.assertTrue(all(len(t)<=4096 for t in texts))
    def test_long_passage_partial_failure(self):
        self.update["message"]["text"]="I goed home. "*45
        result=handle_update(self.update,-123,"fake",self.infer,self.send,lambda p:None)
        self.assertEqual(result,"partial_passage")
        self.assertTrue(all("could not complete" in p["text"] for m,p in self.calls))
    def test_passage_segmentation_and_bounds(self):
        text=("This is a sentence. "*225).strip()
        parts=passage_parts(text)
        self.assertEqual(" ".join(parts),text)
        self.assertTrue(all(len(p)<=480 for p in parts))
        self.assertTrue(all(sum(map(len,b))<=1600 for b in passage_batches(parts)))
        self.assertEqual("".join(message_chunks("a"*7001)),"a"*7001)
    def test_passage_model_truncation_and_missing_paragraphs(self):
        class Client:
            def __init__(self,stop,rows): self.stop=stop; self.rows=rows
            def converse(self,**kw):
                self.limit=kw["inferenceConfig"]["maxTokens"]
                return {"stopReason":self.stop,"output":{"message":{"content":[{"text":json.dumps({"paragraphs":self.rows})}]}}}
        client=Client("max_tokens",[])
        self.assertIsNone(review_passage(["x"*600],client))
        self.assertGreater(client.limit,550)
        self.assertIsNone(review_passage(["one","two"],Client("end_turn",[{"id":1,"corrected":"one","errors":[]}])))
        self.assertIsNone(review_passage(["one"],Client("end_turn",[{"id":1,"corrected":"changed","errors":[]}])))


    def test_portuguese_is_not_correct_english(self):
        from src.inference import local_analysis
        self.assertEqual(language_evidence("Eu gosto muito de você."),"portuguese")
        self.assertEqual(language_evidence("I gosto de you."),"mixed")
        self.assertEqual(language_evidence("I like you very much."),"unknown")
        self.assertEqual(language_evidence("Ai laik iu."),"unknown")
        raw='{"category":"correct","conversational_reply":"Great!"}'
        self.assertEqual(json.loads(guard_language("Eu gosto muito de você.",raw))["category"],"unclear")
        self.assertEqual(json.loads(guard_language("I gosto de you.",raw))["category"],"unclear")
        self.assertEqual(guard_language("I like you very much.",raw),raw)
        self.assertEqual(json.loads(analyze("Bom dia!"))["category"],"portuguese_only")
    def test_full_telegram_length_eligible(self):
        from src.policy import eligible
        self.update["message"]["text"]="x"*4096
        self.assertTrue(eligible(self.update["message"],-123))
        self.update["message"]["text"]+="x"
        self.assertFalse(eligible(self.update["message"],-123))

    def test_foreign_language_not_praised(self):
        samples=["Mi familia no es muy grande, somos cuatro personas.","Texto grande sem erro - ok. Com erro - nok.","Je suis très content de vous rencontrer.","Ich bin sehr froh, dass du hier bist.","今日は学校に行きます。"]
        raw='{"category":"correct","conversational_reply":"Great!"}'
        for sample in samples:
            self.assertTrue(foreign_evidence(sample),sample)
            self.calls.clear()
            self.update["message"]["text"]=sample
            handle_update(self.update,-123,"fake",lambda t:raw,self.send)
            self.assertNotIn("That's correct!",self.calls[0][1]["text"])
            self.assertNotIn("reply_markup",self.calls[0][1])
    def test_foreign_translation_has_english_playback(self):
        self.update["message"]["text"]="Mi familia no es muy grande."
        raw=json.dumps({"category":"foreign_only","source_language":"es","correction":"My family is not very big.","explanation":"This is Spanish. Try English.","conversational_reply":"Tell me more about your family!"})
        self.assertEqual(handle_update(self.update,-123,"fake",lambda t:raw,self.send),"warn")
        self.assertIn("Pronunciation: My family is not very big.",self.calls[0][1]["text"])
        self.assertNotIn("That's correct!",self.calls[0][1]["text"])
    def test_legacy_foreign_playback_blocked(self):
        cb={"id":"cb1","data":"pronounce:v1","from":{"id":7},"message":{"chat":{"id":-123,"type":"supergroup"},"from":{"is_bot":True,"username":"techverseEnglishBot"},"message_id":8,"text":"Old reply\n\n🔊 Pronunciation: Mi familia no es muy grande.\nWould you like to hear the pronunciation?"}}
        self.assertEqual(handle_pronunciation(cb,-123,"fake",self.send,lambda *a:self.fail("foreign playback"),lambda *a:True),"foreign")
    def test_foreign_misclassification_repaired(self):
        class Client:
            calls=0
            def converse(self,**kw):
                self.calls+=1
                data={"category":"correct","source_language":"es"} if self.calls==1 else {"category":"foreign_only","source_language":"es","correction":"My family is not very big.","explanation":"This is Spanish."}
                return {"stopReason":"end_turn","output":{"message":{"content":[{"text":json.dumps(data)}]}}}
        client=Client()
        result=json.loads(analyze("Mi familia no es muy grande.",client))
        self.assertEqual(result["category"],"foreign_only")
        self.assertEqual(result["correction"],"My family is not very big.")
        self.assertEqual(client.calls,2)
    def test_correct_english_with_international_words(self):
        for sample in ["I went to Paris once.","I like pizza and pasta.","My friend is called Maria.","I love you very much."]:
            self.assertFalse(foreign_evidence(sample))

    def test_natural_vocatives_no_paid_inference(self):
        class NoModel:
            def converse(self,**kw): raise AssertionError("known expression must be local")
        for source,expected in [("Bom dia, seu bot desgraçado","Good morning, you damn bot!"),("Boa tarde, seu idiota!","Good afternoon, you idiot!")]:
            result=json.loads(analyze(source,NoModel()))
            self.assertEqual(result["correction"],expected)
            self.assertEqual(result["category"],"portuguese_only")
        self.assertEqual(json.loads(analyze("Good morning, you damn bot!",NoModel()))["category"],"correct")
    def test_natural_idioms_local(self):
        class NoModel:
            def converse(self,**kw): raise AssertionError("known idiom must be local")
        for source,expected in [("Estou com saudade de você.","I miss you."),("Estou morrendo de fome.","I'm starving."),("Estou de saco cheio.","I'm fed up."),("Pode deixar comigo.","Leave it to me.")]:
            self.assertEqual(json.loads(analyze(source,NoModel()))["correction"],expected)
    def test_natural_translation_matches_pronunciation(self):
        self.update["message"]["text"]="Bom dia, seu bot desgraçado"
        self.assertEqual(handle_update(self.update,-123,"fake",analyze,self.send),"warn")
        reply=self.calls[0][1]["text"]
        self.assertIn("Natural English: Good morning, you damn bot!",reply)
        self.assertIn("Pronunciation: Good morning, you damn bot!",reply)
        self.assertNotIn("your bot",reply)
    def test_possessive_not_rewritten_by_local_rule(self):
        class Client:
            def converse(self,**kw):
                return {"stopReason":"end_turn","output":{"message":{"content":[{"text":json.dumps({"category":"foreign_only","source_language":"pt","correction":"Where is your dog?","explanation":"Seu means your here."})}]}}}
        self.assertEqual(json.loads(analyze("Onde está seu cachorro?",Client()))["correction"],"Where is your dog?")

    def test_idiom_calque_repair(self):
        class Client:
            calls=0
            def converse(self,**kw):
                self.calls+=1
                data={"category":"foreign_only","source_language":"pt","correction":"We stepped on the ball with our friend." if self.calls==1 else "We let our friend down.","explanation":"Use an idiomatic equivalent."}
                return {"stopReason":"end_turn","output":{"message":{"content":[{"text":json.dumps(data)}]}}}
        client=Client()
        data=json.loads(analyze("Nós pisamos na bola com nosso amigo.",client))
        self.assertEqual(data["correction"],"We let our friend down.")
        self.assertEqual(client.calls,2)
    def test_literal_football_not_forced_to_idiom(self):
        class Client:
            def converse(self,**kw):
                data={"category":"foreign_only","source_language":"pt","correction":"He stepped on the ball during the match.","explanation":"Literal action in football."}
                return {"stopReason":"end_turn","output":{"message":{"content":[{"text":json.dumps(data)}]}}}
        self.assertEqual(json.loads(analyze("Ele pisou na bola durante o jogo.",Client()))["correction"],"He stepped on the ball during the match.")
    def test_disappointment_idiom_local(self):
        class NoModel:
            def converse(self,**kw): raise AssertionError("local")
        self.assertEqual(json.loads(analyze("Ele pisou na bola comigo.",NoModel()))["correction"],"He let me down.")

    def test_short_foreign_word_translation_no_paid_call(self):
        class NoModel:
            def converse(self,**kw): raise AssertionError("known words use local translation")
        for source,expected in [("Perfeito","Perfect!"),("Perfeita!","Perfect!"),("Excelente","Excellent!"),("Perfecto","Perfect!"),("Parfait","Perfect!"),("Perfetto","Perfect!"),("Wunderbar","Wonderful!"),("ありがとう","Thank you!")]:
            self.assertTrue(foreign_evidence(source),source)
            result=json.loads(analyze(source,NoModel()))
            self.assertEqual(result["correction"],expected)
            self.calls.clear()
            self.update["message"]["text"]=source
            self.assertEqual(handle_update(self.update,-123,"fake",analyze,self.send),"warn")
            reply=self.calls[0][1]["text"]
            self.assertIn("Natural English: "+expected,reply)
            self.assertIn("Pronunciation: "+expected,reply)
            self.assertNotIn("That's correct!",reply)
    def test_unknown_short_word_no_false_praise(self):
        class Client:
            calls=0
            def converse(self,**kw):
                self.calls+=1
                return {"stopReason":"end_turn","output":{"message":{"content":[{"text":'{"category":"correct","source_language":"en","conversational_reply":"Great!"}'}]}}}
        client=Client()
        self.assertEqual(json.loads(analyze("zdravstvuyte",client))["category"],"unclear")
        self.assertEqual(client.calls,2)
        self.update["message"]["text"]="zdravstvuyte"
        handle_update(self.update,-123,"fake",lambda t:'{"category":"correct","source_language":"en"}',self.send)
        self.assertNotIn("That's correct!",self.calls[0][1]["text"])
        self.assertNotIn("reply_markup",self.calls[0][1])
    def test_valid_short_english_still_accepted(self):
        for sample in ("Perfect!","Excellent","Awesome","OK","No","Hotel","Pizza","Serendipity"):
            self.calls.clear()
            self.update["message"]["text"]=sample
            handle_update(self.update,-123,"fake",lambda t:'{"category":"correct","source_language":"en","conversational_reply":"Great!"}',self.send)
            self.assertIn("That's correct!",self.calls[0][1]["text"],sample)
            self.assertIn("reply_markup",self.calls[0][1],sample)
    def test_old_perfeito_pronunciation_blocked(self):
        cb={"id":"cb1","data":"pronounce:v2","from":{"id":7},"message":{"chat":{"id":-123,"type":"supergroup"},"from":{"is_bot":True,"username":"techverseEnglishBot"},"message_id":8,"text":"Old reply\n\n🔊 Pronunciation: Perfeito\nWould you like to hear the pronunciation?"}}
        self.assertEqual(handle_pronunciation(cb,-123,"fake",self.send,lambda *a:self.fail("foreign playback"),lambda *a:True),"foreign")

    def test_bilingual_local_grammar(self):
        class NoModel:
            def converse(self,**kw): raise AssertionError("local rule should not call model")
        data=json.loads(analyze("I goed to school yesterday.",NoModel()))
        self.assertIn("goed",data["literal_pt"])
        self.assertEqual(data["natural_pt"],"Eu fui à escola ontem.")
        self.update["message"]["text"]="I goed to school yesterday."
        handle_update(self.update,-123,"fake",lambda t:analyze(t,NoModel()),self.send)
        reply=self.calls[0][1]["text"]
        self.assertIn("Tradução literal",reply)
        self.assertIn("Sentido da versão em inglês: Eu fui à escola ontem.",reply)
        self.assertEqual(pronunciation_target({"data":"pronounce:v2","from":{"id":7},"message":{"chat":{"id":-123,"type":"supergroup"},"from":{"is_bot":True,"username":"techverseEnglishBot"},"text":reply}},-123),"I went to school yesterday.")
    def test_bilingual_foreign_and_correct_local(self):
        class NoModel:
            def converse(self,**kw): raise AssertionError("local")
        for source,expected in [("Perfeito","Perfeito"),("Perfecto","Perfeito!"),("I like English.","Eu gosto de inglês.")]:
            result=json.loads(analyze(source,NoModel()))
            self.assertEqual(result["literal_pt"],expected)
            self.assertTrue(result["natural_pt"])
    def test_missing_bilingual_fields_retried(self):
        class Client:
            calls=0
            def converse(self,**kw):
                self.calls+=1
                d={"category":"correct","source_language":"en","conversational_reply":"Sure!"}
                if self.calls==2: d.update(literal_pt="Eu gosto de ler.",natural_pt="Eu gosto de ler.")
                return {"stopReason":"end_turn","output":{"message":{"content":[{"text":json.dumps(d)}]}}}
        client=Client()
        data=json.loads(analyze("I like reading.",client))
        self.assertEqual(data["literal_pt"],"Eu gosto de ler.")
        self.assertEqual(client.calls,2)
    def test_bilingual_passage_validation(self):
        class Client:
            def converse(self,**kw):
                d={"paragraphs":[{"id":1,"corrected":"I like books.","source_language":"en","errors":[],"literal_pt":"Eu gosto de livros.","natural_pt":"Eu gosto de livros."}],"conversational_reply":"Nice!"}
                return {"stopReason":"end_turn","output":{"message":{"content":[{"text":json.dumps(d)}]}}}
        result=review_passage(["I like books."],Client())
        self.assertEqual(result["paragraphs"][0]["literal_pt"],"Eu gosto de livros.")
    def test_bilingual_uncertain_preserves_gloss(self):
        self.update["message"]["text"]="Blarg foo"
        raw=json.dumps({"category":"unclear","literal_pt":"[Blarg: desconhecido] [foo: desconhecido]","conversational_reply":"Could you explain what you mean?"})
        handle_update(self.update,-123,"fake",lambda t:raw,self.send)
        self.assertIn("[Blarg: desconhecido]",self.calls[0][1]["text"])
        self.assertNotIn("reply_markup",self.calls[0][1])
