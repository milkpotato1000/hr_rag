"""P012 independent routing, preservation and HTTP interaction expectations."""
import concurrent.futures, contextlib, http.client, io, json, sys, threading, time, unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import comparison, ask_compare, rag_langchain
from serve_compare import LearningServer, error_result
from generation import Generator, load_generation_lock, MODEL

@contextlib.contextmanager
def server(fn):
    srv=LearningServer(0,fn);thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    try:yield srv
    finally:srv.shutdown();srv.server_close();thread.join()

def request(srv,path='/',body=None,headers=None,raw=None):
    conn=http.client.HTTPConnection('127.0.0.1',srv.server_port,timeout=5)
    is_post=body is not None or raw is not None
    payload=raw if raw is not None else json.dumps(body) if is_post else None
    conn.request('POST' if is_post else 'GET',path,payload,headers={'Content-Type':'application/json',**(headers or {})})
    r=conn.getresponse();value=(r.status,r.read(),dict(r.getheaders()));conn.close();return value

def result():return {'status':'abstained','answer':'fixture','citations':[],'reason':'no_context','trace':{'generation_calls':0}}

class LearningRoutes(unittest.TestCase):
    def test_dispatcher_default_and_explicit(self):
        with patch.object(comparison,'direct_ask',side_effect=lambda **kw:result()) as direct,patch.object(rag_langchain,'ask',side_effect=lambda **kw:result()) as lc:
            self.assertEqual(comparison.ask(question='q')['trace']['comparison']['implementation'],'langchain')
            self.assertEqual(comparison.ask(question='q',implementation='direct')['trace']['comparison']['implementation'],'direct')
            comparison.ask(question='q',implementation='langchain')
            self.assertEqual((direct.call_count,lc.call_count),(1,2))
    def test_invalid_dispatcher_never_falls_back(self):
        with patch.object(comparison,'direct_ask') as direct,patch.object(rag_langchain,'ask') as lc:
            for value in [None,'',False,[],{},'hybrid']:
                self.assertEqual(comparison.ask(question='q',implementation=value)['reason'],'input')
            direct.assert_not_called();lc.assert_not_called()
    def test_cli_default_and_explicit(self):
        for flags,expected in [([], 'langchain'),(['--implementation','direct'],'direct'),(['--implementation','langchain'],'langchain')]:
            with patch.object(ask_compare,'ask',return_value=result()) as call,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ask_compare.main(['--question','q',*flags]),0)
            self.assertEqual(call.call_args.kwargs['implementation'],expected)
    def test_cli_invalid_exit_two(self):
        out=io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ask_compare.main(['--question','q','--implementation','bad']),2)
        self.assertEqual(json.loads(out.getvalue())['reason'],'input')
    def test_default_no_context_zero_generation(self):
        generator=Mock()
        r=comparison.ask(question='q',retrieve_fn=lambda *args:([],{}),generator=generator)
        self.assertEqual((r['reason'],r['trace']['generation_calls']),('no_context',0));generator.generate.assert_not_called()
    def test_single_and_pair_generation_limits(self):
        sent=[]
        class API:
            def call(self,route,body):
                sent.append(body)
                return {'model':MODEL,'done':True,'message':{'role':'assistant','content':'{"status":"abstained","answer":"fixture","citations":[]}'}}
        for impl in ['direct','langchain']:
            generator=Generator(api=API(),lock=load_generation_lock());generator.check=lambda:None
            r=comparison.ask(question='q',implementation=impl,retrieve_fn=lambda *args:([{'chunk_id':'birthday-eligibility','score':1}],{}),generator=generator)
            self.assertEqual(r['trace']['generation_calls'],1)
            self.assertTrue(r['trace']['generation']['request_dispatched'])
        self.assertEqual(len(sent),2)
    def test_direct_routes_and_separate_documents(self):
        fn=Mock(return_value=result())
        with server(fn) as srv:
            code,raw,headers=request(srv);self.assertEqual(code,200);learning=raw.decode()
            self.assertIn('data-view="learning"',learning);self.assertIn('aria-current="page"',learning)
            for marker in ['id="implementation"','id="compare"','id="comparison"']:
                self.assertNotIn(marker,learning)
            code,raw,_=request(srv,'/experiments/implementation');self.assertEqual(code,200);experiment=raw.decode()
            for marker in ['id="implementation"','id="compare"','학습으로 돌아가기','data-view="experiment"']:
                self.assertIn(marker,experiment)
            for path in ['/app.js','/style.css','/guide','/api/decision']:self.assertEqual(request(srv,path)[0],200)
            for path in ['/unknown','/experiments','/../runtime-lock.json']:self.assertEqual(request(srv,path)[0],404)
            self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
        fn.assert_not_called()
    def test_http_default_and_explicit(self):
        calls=[]
        with server(lambda **kw:(calls.append(kw),result())[1]) as srv:
            for extra,expected in [({},'langchain'),({'implementation':'direct'},'direct'),({'implementation':'langchain'},'langchain')]:
                self.assertEqual(request(srv,'/api/ask',{'question':'q',**extra})[0],200)
                self.assertEqual(calls[-1]['implementation'],expected)
    def test_http_invalid_security_and_limits(self):
        fn=Mock(return_value=result())
        with server(fn) as srv:
            for val in [None,'',False,[],{},'hybrid']:
                self.assertEqual(request(srv,'/api/ask',{'question':'q','implementation':val})[0],400)
            for bad in [{'question':'x'*4001},{'question':'q','top_k':101},{'question':'q','max_context_chars':24001},{'question':'q','chunks_path':'/tmp/x'}]:
                self.assertEqual(request(srv,'/api/ask',bad)[0],400)
            for raw in ['{"question":"q","top_k":NaN}','{"question":"q","question":"z"}','x'*65537]:
                self.assertEqual(request(srv,'/api/ask',raw=raw)[0],400)
            for headers in [{'Host':'evil.example'},{'Origin':'https://evil.example'}]:
                self.assertEqual(request(srv,'/api/ask',{'question':'q'},headers)[0],403)
            self.assertEqual(request(srv,'/api/ask',{'question':'q'},{'Content-Type':'text/plain'})[0],400)
            self.assertEqual(request(srv,'/api/other',{'question':'q'})[0],404)
        fn.assert_not_called()
    def test_http_status_and_no_fallback(self):
        calls=[]
        def fn(**kw):calls.append(kw);return error_result('fixture',kw['question'])
        with server(fn) as srv:
            for reason,code in [('input',400),('provider',502),('timeout',504),('execution',500)]:
                self.assertEqual(request(srv,'/api/ask',{'question':reason})[0],code)
        self.assertEqual([c['implementation'] for c in calls],['langchain']*4)
    def test_pair_error_and_shared_single_request_lock(self):
        calls=[];active=0;peak=0
        def fn(**kw):
            nonlocal active,peak
            active+=1;peak=max(peak,active);calls.append((kw['question'],kw['implementation']));time.sleep(.04);active-=1
            return error_result('fixture','timeout') if kw['implementation']=='langchain' else result()
        with server(fn) as srv,concurrent.futures.ThreadPoolExecutor(2) as pool:
            pair=pool.submit(request,srv,'/api/compare',{'question':'pair','implementation':'langchain'})
            single=pool.submit(request,srv,'/api/ask',{'question':'single'})
            code,raw,_=pair.result();self.assertEqual(code,200);rows=json.loads(raw)['results']
            self.assertEqual([r['implementation'] for r in rows],['direct','langchain'])
            self.assertEqual([r['result']['status'] for r in rows],['abstained','error'])
            self.assertEqual(single.result()[0],504)
        self.assertEqual(peak,1);start=calls.index(('pair','direct'));self.assertEqual(calls[start:start+2],[('pair','direct'),('pair','langchain')])
if __name__=='__main__':unittest.main()
