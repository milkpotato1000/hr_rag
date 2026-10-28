"""Actual loopback HTTP, offline fake pipeline. Not live model quality tests."""
import concurrent.futures
import http.client
import json
from pathlib import Path
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from serve import LearningServer, error_result, WEB


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        def fake(**kwargs):
            self.calls.append(kwargs)
            if kwargs['question'] in ('provider','timeout','execution','input'):
                return error_result('fixture failure', kwargs['question'])
            return {'status': 'abstained' if kwargs['question']=='missing' else 'answered',
                    'answer':'<img src=x onerror=alert(1)> 가상 답변', 'citations': [], 'reason': None, 'trace':{'fixture':True}}
        self.server=LearningServer(0, fake)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def request(self, body=None, path='/api/ask', method='POST', headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        h={'Content-Type':'application/json',**(headers or {})}
        raw=json.dumps(body) if isinstance(body,dict) else body
        c.request(method,path,body=raw,headers=h)
        r=c.getresponse();data=r.read();status=r.status;response_headers=dict(r.getheaders());c.close()
        return status,data,response_headers

    def test_answer_and_abstain_use_same_pipeline_kwargs(self):
        for question,status in [('normal','answered'),('missing','abstained')]:
            code,raw,_=self.request({'question':question,'retriever':'bm25','top_k':3,'max_context_chars':500})
            self.assertEqual(code,200);self.assertEqual(json.loads(raw)['status'],status)
            self.assertEqual(self.calls[-1],dict(question=question,retriever='bm25',top_k=3,max_context_chars=500))

    def test_http_error_mapping(self):
        for reason,code in [('provider',502),('timeout',504),('execution',500),('input',400)]:
            actual,raw,_=self.request({'question':reason});self.assertEqual(actual,code)
            self.assertEqual(json.loads(raw)['status'],'error')
            self.assertNotEqual(json.loads(raw)['status'],'abstained')

    def test_invalid_json_types_ranges_labels_rejected(self):
        values=['{','null','[]','{"question":"a","question":"b"}',{'question':''},{'question':3},
                {'question':'q','top_k':True},{'question':'q','top_k':0},{'question':'q','top_k':101},
                {'question':'q','max_context_chars':0},{'question':'q','retriever':'hybrid'},
                {'question':'q','relevance':{}},{'question':'x'*4001}]
        for value in values:
            code,raw,_=self.request(value);self.assertEqual(code,400);self.assertEqual(json.loads(raw)['reason'],'input')
        self.assertEqual(self.calls,[])

    def test_routes_types_origin_and_payload_limit(self):
        self.assertEqual(self.request({'question':'q'},path='/unknown')[0],404)
        self.assertEqual(self.request(path='/../generation-lock.json',method='GET')[0],404)
        self.assertEqual(self.request({'question':'q'},headers={'Content-Type':'text/plain'})[0],400)
        self.assertEqual(self.request('x'*65537)[0],400)
        self.assertEqual(self.request({'question':'q'},headers={'Origin':'https://example.com'})[0],403)
        self.assertEqual(self.request({'question':'q'},headers={'Host':'example.com'})[0],403)
        self.assertEqual(self.calls,[])

    def test_static_assets_render_data_as_text(self):
        code,html,headers=self.request(method='GET',path='/')
        self.assertEqual(code,200);self.assertIn('가상 HR 문서 학습용',html.decode())
        self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
        code,js,_=self.request(method='GET',path='/app.js');self.assertEqual(code,200)
        self.assertNotIn('innerHTML',js.decode());self.assertNotIn('insertAdjacentHTML',js.decode())
        self.assertIn('textContent',js.decode())
        for path in ['/style.css','/guide']:
            self.assertEqual(self.request(method='GET',path=path)[0],200)
        _,raw,_=self.request({'question':'normal'})
        self.assertIn('<img src=x onerror=alert(1)>',json.loads(raw)['answer'])

    def test_serializes_pipeline_but_get_stays_responsive(self):
        active=0;peak=0;guard=threading.Lock();entered=threading.Event()
        def fake(**kwargs):
            nonlocal active,peak
            with guard:active+=1;peak=max(peak,active)
            entered.set();time.sleep(.12)
            with guard:active-=1
            return {'status':'answered','answer':'fixture','citations':[],'reason':None,'trace':{}}
        self.server.ask_fn=fake
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(self.request,{'question':'q'}) for _ in range(2)]
            self.assertTrue(entered.wait(2));self.assertEqual(self.request(method='GET',path='/')[0],200)
            self.assertTrue(all(j.result()[0]==200 for j in jobs))
        self.assertEqual(peak,1)


if __name__=='__main__':unittest.main()
