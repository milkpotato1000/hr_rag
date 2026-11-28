import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rag_package import pipeline
from rag_package.storage import read_json, write_json, RagError
from rag_package.workspace import init
from test_llm import config, envelope, KEY

class SelectedPipelineTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ws=Path(tmp.name)/'practice'
        init(self.ws)
        fixed=read_json(self.ws/'fixed.json')
        fixed['llm_config']='provider.json'
        write_json(self.ws/'search.json',fixed)
        write_json(self.ws/'provider.json',config('openai_chat','json_object'))
    def run_case(self,name,question='생일 휴가',execute=True):
        return pipeline.run(self.ws/'sources.json',self.ws/'chunk-fixed.json',self.ws/'search.json',
                            question,self.ws/name,execute=execute)
    def test_api_preview_empty_and_replay(self):
        with patch('rag_package.llm.invoke',side_effect=AssertionError('unexpected model')):
            report=self.run_case('preview',execute=False)
            self.assertEqual(report['plan']['generation']['provider'],'openai_chat')
            self.assertEqual(report['status'],'preview')
            empty=self.run_case('empty','nevermatchedwordabc')
            self.assertEqual(empty['status'],'abstained',empty)
            self.assertEqual(empty['generation_requests'],0)
            self.assertEqual(pipeline.replay(self.ws/'empty'),empty)
        with self.assertRaisesRegex(RagError,'output_exists'):
            self.run_case('empty')
    def test_fixture_answer_and_partial_failure(self):
        def transport(method,url,headers,body,timeout):
            ctx=json.loads(body['messages'][-1]['content'])['contexts'][0]
            return envelope('openai_chat',json.dumps(dict(status='answered',answer='합성 예시',citations=[{'chunk_id':ctx['chunk_id']}])))
        from rag_package.llm import invoke
        with patch('rag_package.llm.invoke',side_effect=lambda *a,**kw:invoke(*a,**dict(kw,transport=transport,key_resolver=lambda _:KEY))):
            success=self.run_case('example')
        self.assertEqual(success['status'],'answered',success)
        self.assertEqual(success['answer']['citations'][0]['quote'],read_json(self.ws/'example/rerank/result.json')['selection']['contexts'][0]['text'])
        with patch.object(pipeline.retrieval,'build',side_effect=RagError('fixture_failure','build')),patch.object(pipeline.rag,'ask',side_effect=AssertionError):
            failed=self.run_case('partial')
        self.assertEqual(failed['failed_stage'],'index')
        self.assertEqual(failed['stages']['search'],'pending')
        self.assertEqual(pipeline.replay(self.ws/'partial'),failed)
        write_json(self.ws/'search.json',{})
        self.assertEqual(self.run_case('invalid')['status'],'failed')
