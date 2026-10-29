import sys,unittest,tempfile,threading,time,json,urllib.request,urllib.error,contextlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import serve_chunking as s
from experiment_common import ExperimentError,config,save_state

class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.patch=patch.object(s,'JOBS',Path(cls.tmp.name)/'jobs');cls.patch.start();s.restart_jobs()
        cls.server=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler);cls.base='http://127.0.0.1:'+str(cls.server.server_port);threading.Thread(target=cls.server.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.patch.stop();cls.tmp.cleanup()
    def call(self,path,body=None,headers=None,raw=None):
        data=raw if raw is not None else json.dumps(body).encode() if body is not None else None
        req=urllib.request.Request(self.base+path,data=data,headers={'Content-Type':'application/json',**(headers or {})})
        try:r=urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:r=e
        return r.status,r.headers,r.read()
    def test_security_and_input_boundaries(self):
        self.assertEqual(self.call('/api/corpora',headers={'Origin':'https://example.com'})[0],403)
        self.assertEqual(self.call('/api/corpora',headers={'Host':'evil.test'})[0],403)
        for path in ['/api/documents/../../etc/passwd','/api/documents/%2e%2e/pdf','/api/documents/unknown/pdf','/api/documents/hr-v4-handbook/pages/24/preview']:self.assertEqual(self.call(path)[0],404)
        self.assertEqual(self.call('/api/chunk-jobs',raw=b'x'*65537)[0],413)
        self.assertEqual(self.call('/api/chunk-jobs',raw=b'{"a":1,"a":2}')[0],400)
        b=dict(corpus_id='source-v4',config='bad',request_id='fixture-config-1',fresh=True);self.assertEqual(self.call('/api/chunk-jobs',b)[0],422)
        b.update(config='fixed-400-80',corpus_id='source-v3');self.assertEqual(self.call('/api/chunk-jobs',b)[0],409)
    def test_registered_pdf_preview_and_headers(self):
        status,headers,body=self.call('/api/documents/hr-v4-handbook/pdf');self.assertEqual(status,200);self.assertTrue(body.startswith(b'%PDF'));self.assertEqual(headers['X-Content-Type-Options'],'nosniff');self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
        self.assertEqual(self.call('/api/documents/hr-v4-handbook/pages/1/preview')[0],200)
    def test_job_failure_idempotency_and_restart(self):
        b=dict(corpus_id='source-v4',config=config('fixed-400-80'),request_id='failure-fixture-0001',fresh=True)
        with patch.object(s,'work_lock',contextlib.nullcontext),patch.object(s,'build',side_effect=ExperimentError('provider','controlled provider failure')):
            j=s.start_job('chunk',b)
            for _ in range(100):
                j=s.read_json(s.JOBS/(j['job_id']+'.json'))
                if j['status']=='FAILED':break
                time.sleep(.01)
        self.assertEqual(j['status'],'FAILED');self.assertEqual(j['reason'],'provider');self.assertEqual(s.start_job('chunk',b)['job_id'],j['job_id'])
        with self.assertRaisesRegex(ExperimentError,'request_id'):s.start_job('chunk',{**b,'fresh':False})
        j.update(status='RUNNING');save_state(s.JOBS/(j['job_id']+'.json'),j);s.restart_jobs();self.assertEqual(s.read_json(s.JOBS/(j['job_id']+'.json'))['status'],'INTERRUPTED')
    def test_holdout_and_unknown_query_blocked_before_retrieval(self):
        q=next(q for q in s.read_json(s.EXP/'dataset.json')['questions'] if q['split']=='holdout')
        b=dict(a_run_id='none',b_run_id='none',retriever='bm25',top_k=5,budget_chars=800,query_id=q['query_id'])
        self.assertEqual(self.call('/api/search-comparisons',b)[0],400)
        b['query_id']='unknown';self.assertEqual(self.call('/api/search-comparisons',b)[0],404)
    def test_symlink_run_rejected(self):
        with tempfile.TemporaryDirectory() as t,patch.object(s,'ARTIFACTS',Path(t)):
            (Path(t)/('chunk-'+'a'*32)).symlink_to(Path(t),target_is_directory=True)
            with self.assertRaises(ExperimentError):s.registered_run('chunk-'+'a'*32)
if __name__=='__main__':unittest.main()
