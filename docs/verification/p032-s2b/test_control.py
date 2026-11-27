"""Independent failure tests: fake dispatch observations + owned dummy children.

No model/backend is used; real installed compare error-continuation is exercised
with deterministic BM25 fixture computation and explicit test-only worker records.
"""
from pathlib import Path
import unittest,tempfile,importlib.util,sys,json,copy,contextlib,shutil
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('runtime',Path(__file__).with_name('runtime.py'));rt=importlib.util.module_from_spec(spec);spec.loader.exec_module(rt)
ctl=rt.module('control')
from rag_package.storage import write_json,read_json,RagError,require,verify,seal
from rag_package import rag,retrieval,owned_worker,chunk_artifact
from rag_package.documents import snapshot
from rag_package.candidates import copy_artifact
from rag_package.ui_registry import atomic_json

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.path=self.root/'ledger.json';write_json(self.path,ctl.initial());self.now=100
        self.c=ctl.Control(self.path,clock=lambda:self.now,disk=lambda:4*1024**3);self.c.claim();self.dispatches=0
    def tearDown(self):self.tmp.cleanup()
    def computed(self,items):
        self.c.before_spawn(['python','-m','rag_package.embedding_worker']);self.dispatches+=1
        self.c.after_worker({'workers_started':1,'worker_exited':True,'resume_safe':True,'completed':True,'samples':[]})
        self.c.computed(items)
    def op(self,label,items=1,fail=None,cp=None):
        def run():
            self.computed(items)
            if fail:raise fail
            return 'ok'
        return self.c.operation(label,items,run,lambda r:None,cp or (lambda r:None))
    def boundary(self):self.op('semantic-boundary',567)
    def test_exact_limits_and_gate(self):
        self.boundary()
        for m in ctl.METHODS:
            self.op(m+'-index',{'fixed':201,'recursive':257,'structure':264,'semantic':567}[m])
            for q in range(1,11):self.op(m+'-gt'+str(q).zfill(2))
        self.c.complete();self.assertEqual(self.c.state['reserved_workers'],45);self.assertEqual(self.c.state['reserved_items'],1896)
        self.assertEqual(self.c.state['gates'],list(ctl.METHODS))
        with self.assertRaises(RagError):ctl.Control(self.path)
    def test_deadline_no_extension(self):
        self.boundary();self.now=3700
        with self.assertRaisesRegex(RagError,'s2b_deadline'):self.op('fixed-index',201)
        self.assertEqual(self.c.state['deadline'],3700);self.assertEqual(self.dispatches,1)
        with self.assertRaises(RagError):ctl.Control(self.path)
    def test_caps_before_spawn(self):
        for field,value,error in [('reserved_workers',45,'worker_budget'),('reserved_items',1896,'item_budget')]:
            with self.subTest(field=field):
                p=self.root/(field+'.json');write_json(p,ctl.initial());c=ctl.Control(p,disk=lambda:4*1024**3);c.claim();c.state[field]=value
                with self.assertRaisesRegex(RagError,error):c.operation('semantic-boundary',567,lambda:c.before_spawn(['x','rag_package.embedding_worker']),lambda _:None,lambda _:None)
                self.assertEqual(c.state['status'],'halted')
    def test_gate_order_and_parallel(self):
        self.boundary()
        with self.assertRaisesRegex(RagError,'order_mismatch'):self.op('fixed-gt03')
        self.assertEqual(self.dispatches,1)
    def test_disk_floor(self):
        self.c.disk=lambda:1
        with self.assertRaisesRegex(RagError,'disk_floor'):self.boundary()
        self.assertEqual(self.dispatches,0)
    def test_unknown_worker_and_logical_error(self):
        def run():
            self.c.before_spawn(['x','rag_package.embedding_worker']);self.dispatches+=1
            self.c.after_worker({'workers_started':1,'worker_exited':True,'resume_safe':True,'completed':True})
            raise RagError('invalid_worker_json','embedding')
        with self.assertRaisesRegex(RagError,'invalid_worker_json'):self.c.operation('semantic-boundary',567,run,lambda _:None,lambda _:None)
        self.assertIsNone(self.c.state['operations'][0]['completed_items'])
        with self.assertRaises(RagError):self.op('fixed-index',201)
        self.assertEqual(self.dispatches,1)
    def test_unreaped_worker(self):
        def run():
            self.c.before_spawn(['x','rag_package.embedding_worker']);self.c.after_worker({'workers_started':1,'worker_exited':False,'resume_safe':False});self.c.computed(567)
        with self.assertRaisesRegex(RagError,'not_reaped'):self.c.operation('semantic-boundary',567,run,lambda _:None,lambda _:None)
        self.assertEqual(self.c.state['status'],'halted')
    def test_journal_write_failure_and_restart(self):
        def fail(*args):raise OSError('disk write')
        self.c.persist=fail
        with self.assertRaises(OSError):self.boundary()
        self.assertTrue(self.c.marker.exists());self.assertEqual(self.dispatches,0)
        with self.assertRaises(RagError):ctl.Control(self.path)
    def test_pre_operation_tamper_latches(self):
        for kind in ('source','profile','artifact'):
            try:self.c.protect(lambda:(_ for _ in ()).throw(RagError('changed_'+kind,'input')))()
            except RagError:pass
        self.assertEqual(self.dispatches,0);self.assertEqual(self.c.state['status'],'halted')
    def test_actual_frozen_file_tamper(self):
        folders={k:self.root/k for k in ('S1','S2a','input','scripts','protected')}
        for folder in folders.values():folder.mkdir();(folder/'file').write_text('frozen')
        with patch.object(rt,'S1',folders['S1']),patch.object(rt,'S2A',folders['S2a']),patch.object(rt,'RUN',self.root),patch.object(rt,'E',folders['scripts']),patch.object(rt,'ROOT',folders['protected']):
            for filename in ('source-canonical.txt','profile.json','artifact-manifest.json'):
                target=folders['input']/filename;target.write_text('original')
                manifest={'files':{k:rt.hashes(v) for k,v in folders.items()}}
                rt.check_frozen(manifest);target.write_text('tampered')
                with self.assertRaisesRegex(RagError,'input_changed'):rt.check_frozen(manifest)
                target.write_text('original')
    def test_missing_gate_and_concurrent_operation(self):
        self.boundary();self.op('fixed-index');self.op('fixed-gt01');self.op('fixed-gt02');self.c.state['gates']=[]
        with self.assertRaisesRegex(RagError,'missing_two_question_gate'):self.op('fixed-gt03')
        self.assertEqual(self.dispatches,4)
    def test_record_failure_after_reaped_worker(self):
        def run():
            self.c.before_spawn(['x','rag_package.embedding_worker']);self.dispatches+=1
            self.c.persist=lambda *a:(_ for _ in ()).throw(OSError('journal disk'))
            self.c.after_worker({'workers_started':1,'worker_exited':True,'resume_safe':True,'completed':True})
        with self.assertRaises(OSError):self.c.operation('semantic-boundary',567,run,lambda _:None,lambda _:None)
        self.assertTrue(self.c.marker.exists());self.assertTrue(self.c.state['operations'][0]['observation']['worker_exited'])
        self.assertIsNone(self.c.state['operations'][0]['completed_items'])
        with self.assertRaises(RagError):self.op('fixed-index')
        self.assertEqual(self.dispatches,1)
    def compare_fixture(self,failure):
        # Actual compare catches RagError and continues; protected wrappers must not dispatch.
        self.boundary();base=self.root
        (base/'doc.txt').write_text('생일 휴가는 매년 1일입니다. 신청 기한은 3영업일 전입니다.\n'*30)
        write_json(base/'sources.json',{'schema_version':1,'documents':[{'document_id':'doc','format':'txt','path':'doc.txt','title':'synthetic','synthetic':True}]})
        snapshot(base/'sources.json',base/'snapshot')
        shutil.copyfile(rt.S2A/'run001/configs/llm-local-example.json',base/'llm.json')
        configs=[]
        for method in ('fixed','recursive'):
            p=base/(method+'.json');write_json(p,{'schema_version':1,'chunking':{'method':method,'size_chars':256,'overlap_chars':64},'retrieval':{'method':'bm25','top_k':5,'context_budget_chars':2000},'llm_config':'llm.json'});configs.append(p)
        qs=[{'id':'gt'+str(n).zfill(2),'question':'생일 휴가 '+str(n)} for n in range(1,11)];write_json(base/'questions.json',qs)
        old_build,old_ask,old_seal=rag.build,rag.ask,rag.seal
        def check(src,dest,kind):
            if failure=='checkpoint' and dest.name=='gt02':raise OSError('checkpoint disk')
            copy_artifact(src,dest,kind)
        def build(s,p,out,**kw):
            m=retrieval.config(p)[0]['chunking']['method']
            def run():self.computed(1);return old_build(s,p,out,**kw)
            return self.c.operation(m+'-index',1,run,lambda _:verify(out,'build'),lambda _:check(out,base/'checkpoint'/m/'build','build'))
        def ask(b,p,q,out,**kw):
            m=retrieval.config(p)[0]['chunking']['method'];qid=kw['question_id']
            def run():
                self.computed(1)
                if failure=='third_question' and qid=='gt03':raise RagError('third_question_json','embedding')
                if failure=='cancel' and qid=='gt03':raise KeyboardInterrupt()
                return old_ask(b,p,q,out,**kw)
            return self.c.operation(m+'-'+qid,1,run,lambda r:require(r['status']=='preview','logical_failure','test'),lambda _:check(out,base/'checkpoint'/m/qid,'answer'))
        def sealer(path,identity,*a):
            if failure=='publication' and identity['kind']=='comparison':raise OSError('publication disk')
            return old_seal(path,identity,*a)
        with patch.object(rag,'build',self.c.protect(build)),patch.object(rag,'ask',self.c.protect(ask)),patch.object(rag,'seal',sealer):
            try:
                result=rag.compare(base/'snapshot',configs,base/'questions.json',base/'comparison')
                if any(x['status']=='failed' for x in result['rows']):self.c.halt(RagError('comparison_failed'))
            except BaseException as e:self.c.halt(e)
        before=self.dispatches
        with self.assertRaises(RagError):self.op('semantic-index')
        self.assertEqual(self.dispatches,before);self.assertEqual(self.c.state['status'],'halted')
        if not (base/'checkpoint/fixed/gt01/manifest.json').exists():print('fixture diagnostic',failure,self.c.state,flush=True)
        verify(base/'checkpoint/fixed/build','build');verify(base/'checkpoint/fixed/gt01','answer')
        if failure!='checkpoint':verify(base/'checkpoint/fixed/gt02','answer')
        return before
    def test_third_question_stops_real_compare_dispatch(self):self.assertEqual(self.compare_fixture('third_question'),5)
    def test_checkpoint_error_preserves_prior_results(self):self.assertEqual(self.compare_fixture('checkpoint'),4)
    def test_publication_error_preserves_all_checkpoints(self):self.assertEqual(self.compare_fixture('publication'),23)
    def test_cancel_preserves_prior_checkpoints(self):self.assertEqual(self.compare_fixture('cancel'),5)
    def test_owned_dummy_json_failure_reaped(self):
        before=self.c.before_spawn
        # Only the test maps a dummy child command to the registered worker label.
        self.c.before_spawn=lambda cmd:before(['test-only','rag_package.embedding_worker'])
        obs={}
        def run():
            with owned_worker.execution_scope(self.c):
                stdout,_,rc=owned_worker.communicate_owned([sys.executable,'-c','import sys;sys.stdin.read();print("not-json")'],'',5,env={},observation=obs,monitor=lambda:{'pressure':'normal'},rss_reader=lambda pid:1024)
            self.assertEqual(rc,0);json.loads(stdout)
        with self.assertRaises(ValueError):self.c.operation('semantic-boundary',567,run,lambda _:None,lambda _:None)
        self.assertTrue(obs['worker_exited']);self.assertTrue(obs['resume_safe']);self.assertEqual(self.c.state['status'],'halted')
    def test_owned_dummy_rss_stop(self):
        before=self.c.before_spawn;self.c.before_spawn=lambda cmd:before(['test-only','rag_package.embedding_worker']);obs={}
        def run():
            with owned_worker.execution_scope(self.c):
                return owned_worker.communicate_owned([sys.executable,'-c','import time;time.sleep(10)'],'',5,env={},observation=obs,monitor=lambda:{'pressure':'normal'},rss_reader=lambda pid:4*1024**3)
        with self.assertRaisesRegex(RagError,'rss_limit'):self.c.operation('semantic-boundary',567,run,lambda _:None,lambda _:None)
        self.assertTrue(obs['worker_exited']);self.assertTrue(obs['resume_safe'])

if __name__=='__main__':unittest.main()
