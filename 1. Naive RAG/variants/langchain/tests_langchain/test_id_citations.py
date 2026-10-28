"""Independent P009 boundary cases; mock outputs are not model-quality evidence."""
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.append(str(Path(__file__).resolve().parents[1] / 'tests'))
import generation as g
import rag_langchain as rag
import setup_generation as setup
from test_rag import FakeGenerator, ANSWER, CID, ranking

TEXT = '  한글 "원문"\n이월한 연차의 사용 기한\n은 다음 해 3월 31일이다.\n '

def context(cid='only-a', text=TEXT):
    return dict(chunk_id=cid, document_id='doc', version='2', title='원문', text=text, source='synthetic://fixture')

def answer(*ids):
    return dict(status='answered', answer='테스트 답변', citations=[{'chunk_id': i} for i in ids])

class IDContractTests(unittest.TestCase):
    def test_full_original_bytes_and_selected_order(self):
        contexts = [context(), context('only-b', '둘째\n원문')]
        result, errors = rag.validate_answer(json.dumps(answer('only-b', 'only-a')), contexts)
        self.assertEqual(errors, [])
        self.assertEqual([c['chunk_id'] for c in result['citations']], ['only-b', 'only-a'])
        self.assertEqual(result['citations'][1]['quote'].encode(), TEXT.encode())
        self.assertEqual(result['citations'][0], dict(chunk_id='only-b', quote='둘째\n원문', document_id='doc', version='2', title='원문', source='synthetic://fixture'))

    def test_reject_ids_duplicates_extra_fields_and_abstention_citations(self):
        cases = [answer(v) for v in ('', ' ', 'missing', 1, None, [], {}, True)]
        cases += [answer('only-a','only-a'), answer(), {**answer('only-a'), 'status':'abstained'}]
        for extra in ('quote','source','title'):
            value=answer('only-a'); value['citations'][0][extra]='forged'; cases.append(value)
        cases += [{**answer('only-a'), 'extra':1}, {'status':[], 'answer':'a','citations':[]}]
        for value in cases:
            with self.subTest(value=value):
                result, errors=rag.validate_answer(json.dumps(value), [context()])
                self.assertIsNone(result); self.assertTrue(errors)

    def test_bad_context_is_execution_error_before_provider(self):
        for contexts in ([context(),context()], [context(text=None)], [context(text=' ')], [context(text=[])], [context(cid='')]):
            provider=FakeGenerator()
            with patch('rag_langchain.select_context',return_value=(contexts,[],0)):
                result=rag.ask('q',retrieve_fn=ranking,generator=provider)
            self.assertEqual((result['status'],result['reason'],provider.calls),('error','execution',0))

    def test_no_context_does_not_claim_schema_was_sent(self):
        result=rag.ask('q',retrieve_fn=ranking,generator=FakeGenerator(),max_context_chars=1)
        self.assertEqual(result['trace']['generation_calls'],0)
        self.assertNotIn('generation',result['trace'])

    def test_snapshot_survives_file_and_selected_list_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'chunks.jsonl'; row={**context(), 'synthetic':True}
            path.write_text(json.dumps(row))
            selected=[context()]
            class Mutator(FakeGenerator):
                def generate(self,messages,allowed_ids,*,on_send=None):
                    path.write_text(json.dumps({**row,'text':'changed on disk'}))
                    selected[0]['text']='changed in selected list'
                    return super().generate(messages,allowed_ids,on_send=on_send)
            with patch('rag_langchain.select_context',return_value=(selected,[],100)):
                result=rag.ask('q',chunks_path=path,retrieve_fn=lambda *a: ([],{}),generator=Mutator(answer('only-a')))
            self.assertEqual(result['citations'][0]['quote'],TEXT)
            self.assertEqual(result['trace']['contexts'][0]['text'],TEXT)
            self.assertEqual(result['trace']['citation_assembly'][0]['text_sha256'],hashlib.sha256(TEXT.encode()).hexdigest())

    def test_provider_spy_schema_trace_and_concurrent_isolation(self):
        lock=g.load_generation_lock(); before=copy.deepcopy(lock); template=copy.deepcopy(g.SCHEMA)
        barrier=threading.Barrier(2)
        with tempfile.TemporaryDirectory() as tmp:
            def run(cid, wait):
                path=Path(tmp)/(cid+'.jsonl'); path.write_text(json.dumps({**context(cid), 'synthetic':True}))
                sent=[]
                class API:
                    def call(self, endpoint, body):
                        if endpoint != '/api/chat': raise AssertionError(endpoint)
                        if wait: barrier.wait(timeout=5)
                        sent.append(copy.deepcopy(body))
                        return {'model':g.MODEL,'done':True,'message':{'role':'assistant','content':json.dumps(answer(cid))}}
                provider=g.Generator(api=API(),lock=lock); provider.check=Mock()
                result=rag.ask('q',chunks_path=path,retrieve_fn=lambda *a: ([{'chunk_id':cid,'score':1}],{}),generator=provider)
                actual=sent[0]; trace=result['trace']['generation']
                self.assertEqual(actual['messages'],result['trace']['prompt']['messages'])
                self.assertEqual(actual['format'],trace['request']['format'])
                self.assertEqual(actual['format']['properties']['citations']['items']['properties']['chunk_id']['enum'],[cid])
                self.assertEqual(trace['allowed_ids'],[cid]); self.assertTrue(trace['request_dispatched'])
                self.assertEqual(trace['schema_sha256'],g.digest_text(json.dumps(actual['format'],ensure_ascii=False,sort_keys=True)))
                self.assertEqual(result['citations'][0]['chunk_id'],cid)
            run('seq-a',False); run('seq-b',False)
            with ThreadPoolExecutor(2) as pool:
                futures=[pool.submit(run,cid,True) for cid in ['parallel-a','parallel-b']]
                for f in futures: f.result()
        self.assertEqual(lock,before); self.assertEqual(g.SCHEMA,template)

    def test_enum_excludes_retrieved_not_transmitted(self):
        result=rag.ask('q',retrieve_fn=ranking,generator=FakeGenerator(),top_k=1)
        trace=result['trace']['generation']
        self.assertEqual(trace['allowed_ids'],[CID])
        self.assertEqual(trace['request']['format']['properties']['citations']['items']['properties']['chunk_id']['enum'],[CID])

    def test_preflight_failure_does_not_claim_dispatch(self):
        provider=g.Generator(); provider.check=Mock(side_effect=ValueError('metadata changed'))
        result=rag.ask('q',retrieve_fn=ranking,generator=provider)
        self.assertEqual(result['reason'],'provider')
        self.assertIsNone(result['trace']['generation']['request'])
        self.assertFalse(result['trace']['generation']['request_dispatched'])

    def test_empty_schema_and_reject_bad_allowlists(self):
        lock=g.load_generation_lock(); request=g.request_for_ids(lock,[])
        self.assertEqual(request['format']['properties']['citations']['maxItems'],0)
        self.assertNotIn('enum',request['format']['properties']['citations']['items']['properties']['chunk_id'])
        for ids in (['a','a'],[1],[None],[[]],['']):
            with self.assertRaises(ValueError): g.request_for_ids(lock,ids)

    def test_lock_version_and_rules_are_enforced(self):
        lock=g.load_generation_lock()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'lock.json'
            for field,value in [('schema_version',1),('response_contract','old'),('dynamic_schema_rule','other')]:
                path.write_text(json.dumps({**lock,field:value}))
                with self.assertRaises(ValueError): g.load_generation_lock(path)

    def test_setup_reuses_bytes_probes_empty_context_and_refuses_metadata_change(self):
        lock=g.load_generation_lock(); api=Mock(); api.call.return_value={'models':[{'name':g.MODEL}]}
        sent=[]
        def generate(self,messages,ids,*,on_send=None):
            self.assert_ids=ids; sent.append(ids); on_send(g.request_for_ids(self.lock,ids))
            return json.dumps({'status':'abstained','answer':'API 확인','citations':[]}),{}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'lock.json'; original=json.dumps(lock).encode(); path.write_bytes(original)
            with patch.object(setup,'LOCK',path), patch.object(setup,'load_lock'), patch.object(setup.runtime,'start'), patch.object(setup,'LocalAPI',return_value=api), patch.object(setup,'metadata',return_value=lock['model']), patch.object(g.Generator,'generate',generate), patch('sys.stdout',new_callable=io.StringIO) as out:
                setup.setup()
                self.assertEqual(path.read_bytes(),original)
                self.assertEqual(sent,[[]])
                self.assertEqual(json.loads(out.getvalue())['request']['format']['properties']['citations']['maxItems'],0)
                with patch.object(setup,'metadata',return_value={**lock['model'],'digest':'bad'}):
                    with self.assertRaisesRegex(ValueError,'refusing lock overwrite'): setup.setup()
                self.assertEqual(path.read_bytes(),original)

if __name__=='__main__': unittest.main()
