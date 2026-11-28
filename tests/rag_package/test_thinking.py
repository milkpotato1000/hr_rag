import json
import unittest
from test_llm import config, envelope, Fake, MESSAGES
from rag_package.llm import invoke, preview, validate_config, ValidationError

class ThinkingTests(unittest.TestCase):
    def test_final_only(self):
        for flag,hidden,content,finish,ok in [
            (True,'private-sentinel','{"x":1}','stop',True),
            (False,'private-sentinel','{}','stop',False),
            (True,None,'{}','stop',False),
            (True,'private-sentinel','<think>private-sentinel</think>{}','stop',False),
            (True,'private-sentinel','','stop',False),
            (True,'private-sentinel','{}','length',False),
            (True,'private-sentinel','{"x":1,"x":2}','stop',False)]:
            with self.subTest(flag=flag,finish=finish):
                cfg=config(response_mode='json_object')
                cfg['profiles']['one']['think']=flag
                raw=envelope(content=content,finish=finish)
                raw['message']['thinking']=hidden
                answer=invoke(cfg,'generation',MESSAGES,transport=Fake(response=raw))
                self.assertEqual(answer['status']=='complete',ok)
                self.assertNotIn('private-sentinel',json.dumps(answer))
    def test_profile(self):
        cfg=config()
        default=preview(cfg,'generation',MESSAGES)
        cfg['profiles']['one']['think']=False
        self.assertEqual(default,preview(cfg,'generation',MESSAGES))
        for provider,value in [('ollama',None),('ollama',1),('ollama','true'),('openai_chat',False),('anthropic_messages',True)]:
            cfg=config(provider)
            cfg['profiles']['one']['think']=value
            with self.assertRaises(ValidationError):validate_config(cfg)
