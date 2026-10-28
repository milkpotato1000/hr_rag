import json,sys,unittest,threading,time,http.client,concurrent.futures
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from serve_compare import LearningServer,error_result
class ComparisonHTTP(unittest.TestCase):
 def setUp(self):
  self.calls=[];self.active=0;self.peak=0
  def fake(**kw):
   self.active+=1;self.peak=max(self.peak,self.active);self.calls.append(kw);time.sleep(.02);self.active-=1
   if kw['question']=='one-error' and kw['implementation']=='langchain':return error_result('fixture timeout','timeout')
   if kw['question']=='raise' and kw['implementation']=='direct':raise RuntimeError('fixture')
   return {'status':'abstained','answer':'fixture','citations':[],'reason':'no_context','trace':{'generation_calls':0}}
  self.server=LearningServer(0,fake);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join()
 def request(self,body,path='/api/ask',headers=None):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5);c.request('POST',path,json.dumps(body),headers={'Content-Type':'application/json',**(headers or {})});r=c.getresponse();code=r.status;data=json.loads(r.read());c.close();return code,data
 def test_default_and_invalid_selection(self):
  self.assertEqual(self.request({'question':'q'})[0],200);self.assertEqual(self.calls[-1]['implementation'],'direct')
  for value in ['hybrid','',None,[],{}]:self.assertEqual(self.request({'question':'q','implementation':value})[0],400)
  for extra in [{'corpus':'../../'},{'chunks_path':'/tmp/file'},{'relevance':{}}]:self.assertEqual(self.request({'question':'q',**extra})[0],400)
 def test_pair_failure_retained_order_and_lock(self):
  with concurrent.futures.ThreadPoolExecutor(2) as pool:
   jobs=[pool.submit(self.request,{'question':'one-error'},'/api/compare') for _ in range(2)]
   for f in jobs:
    code,data=f.result();self.assertEqual(code,200);self.assertEqual([x['implementation'] for x in data['results']],['direct','langchain']);self.assertEqual([x['result']['status'] for x in data['results']],['abstained','error']);self.assertEqual(data['results'][1]['result']['reason'],'timeout')
  self.assertEqual(self.peak,1);self.assertEqual([x['implementation'] for x in self.calls],['direct','langchain']*2)
 def test_exception_does_not_drop_other_side(self):
  code,data=self.request({'question':'raise'},'/api/compare');self.assertEqual(code,200);self.assertEqual([x['result']['status'] for x in data['results']],['error','abstained'])
 def test_origin_and_limits(self):
  self.assertEqual(self.request({'question':'q'},headers={'Origin':'https://example.org'})[0],403)
  self.assertEqual(self.request({'question':'q','top_k':101})[0],400)
  self.assertEqual(self.request({'question':'x'*65537})[0],400)
if __name__=='__main__':unittest.main()
