import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from rag_package.storage import RagError, write_json
from rag_package.ui_registry import Registry
from rag_package.ui_jobs import Jobs
from rag_package.workspace import init
from test_llm import config, DIGEST, envelope

class PipelineJobTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ws=Path(tmp.name).resolve()/'practice'
        init(self.ws)
        write_json(self.ws/'configured.json',config('ollama','json_object'))
        self.registry=Registry(self.ws,[self.ws/'configured.json'],self.ws/'sources.json',
                               chunk_configs=[self.ws/'chunk-fixed.json',self.ws/'chunk-llm.json'])
        self.payload=dict(kind='pipeline',request_id=str(uuid.uuid4()),input_ids=list(self.registry.inputs),
                          question='생일 휴가',chunk_config_id=next(iter(self.registry.chunk_configs)),
                          llm_config_id=next(iter(self.registry.data['configs'])),embedding_config_id=None,
                          reranker_config_id=None,execute=True,retrieval=dict(method='bm25',top_k=5,
                          context_budget_chars=4000,candidate_k=20,rrf_k=60))
    def test_permission_matrix(self):
        with self.assertRaisesRegex(RagError,'model_execution_disabled'):
            Jobs(self.registry).submit(self.payload)
        jobs=Jobs(self.registry,allow_model=True)
        for override,error in [
            ({'retrieval':dict(self.payload['retrieval'],method='dense')},'retrieval_execution_required'),
            ({'reranker_config_id':'abc'},'reranking_execution_disabled'),
            ({'chunk_config_id':list(self.registry.chunk_configs)[1]},'chunking_execution_disabled'),
            ({'input_ids':['/tmp/foreign']},'invalid_id')]:
            with self.subTest(expected=error),self.assertRaisesRegex(RagError,error):
                jobs.submit(dict(self.payload,**override))
    def test_same_request_and_busy(self):
        arrived=threading.Event()
        release=threading.Event()
        calls=[]
        def transport(method,url,headers,body,timeout):
            if method=='GET':
                return {'models':[{'name':'fixture-model','digest':DIGEST}]}
            calls.append(method)
            arrived.set()
            assert release.wait(8)
            ctx=json.loads(body['messages'][-1]['content'])['contexts'][0]
            return envelope('ollama',json.dumps({'status':'answered','answer':'합성 답변','citations':[{'chunk_id':ctx['chunk_id']}]}))
        jobs=Jobs(self.registry,allow_model=True,transport=transport)
        first,new=jobs.submit(self.payload)
        self.assertTrue(new)
        try:
            self.assertTrue(arrived.wait(8))
            prior,new=jobs.submit(self.payload)
            self.assertFalse(new)
            self.assertEqual(prior['id'],first['id'])
            with self.assertRaisesRegex(RagError,'busy'):
                jobs.submit(dict(self.payload,request_id=str(uuid.uuid4())))
        finally:
            release.set()
            jobs.thread.join(8)
        self.assertEqual(jobs.get(first['id'])['status'],'completed')
        restarted=Jobs(self.registry,allow_model=True,transport=transport)
        prior,new=restarted.submit(self.payload)
        self.assertFalse(new)
        self.assertEqual(prior['id'],first['id'])
        self.assertEqual(calls,['POST'])
