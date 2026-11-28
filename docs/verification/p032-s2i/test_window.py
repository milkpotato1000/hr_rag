import json
import unittest
from diagnostic import evaluate
from runtime import E, DIGEST, read
class WindowTests(unittest.TestCase):
    def test_valid_and_rejected_responses(self):
        window=read(E/'window.json')
        profile=read(E/'profile.json')
        ids=[unit['id'] for unit in window['units']]
        cases=[(ids,'stop',None),(['foreign',*ids],'stop','invalid_boundaries'),([ids[1],ids[0],*ids[2:]],'stop','invalid_boundaries'),([ids[0],*ids],'stop','invalid_boundaries'),(ids[:-1],'stop','invalid_boundaries'),(ids[-1:],'stop','boundary_size_exceeded'),(ids,'length','provider_truncated')]
        for ends,reason,error in cases:
            with self.subTest(error=error):
                posts=[]
                def send(method,url,headers,body,timeout):
                    if method=='GET':
                        return {'models':[{'name':'qwen3:4b','digest':DIGEST}]}
                    posts.append(body)
                    return {'model':'qwen3:4b','done':True,'done_reason':reason,'message':{'role':'assistant','thinking':'private-fixture','content':json.dumps({'end_unit_ids':ends})}}
                result=evaluate(window,profile,send)
                self.assertEqual(posts,[window['request']['body']])
                self.assertEqual(result['error'],error)
                self.assertNotIn('private-fixture',json.dumps(result))
                if error is None:
                    self.assertEqual([(s['start'],s['end']) for s in result['spans']],[(u['start'],u['end']) for u in window['units']])
                    self.assertEqual(''.join(u['text'] for u in window['units']),window['source_text'])
