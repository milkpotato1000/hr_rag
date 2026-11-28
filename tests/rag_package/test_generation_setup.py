from pathlib import Path
import tempfile
import unittest

from rag_package import llm_setup
from rag_package.llm.config import ValidationError
from rag_package.storage import RagError, read_json, write_json


class GenerationSetupTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.digest='2'*64
        self.calls=[]

    def send(self,method,url,headers,body,timeout):
        self.calls.append((method,url))
        if url.endswith('/api/tags'):
            return {'models':[{'name':'qwen3:4b','digest':self.digest,'ignored':'private metadata'}]}
        self.assertTrue(url.endswith('/api/show'))
        return {'model_info':{},'details':{'quantization_level':'Q4_K_M' if self.digest==llm_setup.HANDBOOK_DIGEST else 'Q8_0'}}

    def test_same_alias_different_weights(self):
        for folder,digest,origin in [('other','2'*64,'unknown'),('known',llm_setup.HANDBOOK_DIGEST,'historical_digest_match')]:
            self.digest=digest
            out=self.root/folder
            result=llm_setup.setup_generation('ollama','qwen3:4b',out,inspect_local=True,transport=self.send)
            p=read_json(out/'model.json')['profiles']['local']
            self.assertEqual(p['identity']['expected_digest'],digest)
            self.assertEqual(result['inspection'][0]['origin'],origin)
            self.assertEqual(p.get('think'),True if folder=='known' else None)
            if folder=='other':
                self.assertEqual(p['identity']['hf_id'],'unknown')
                self.assertEqual(p['identity']['quantization'],'Q8_0')
        self.assertEqual(len(self.calls),4)

    def test_no_server_needed_for_api_or_offline_local(self):
        for provider in ('openai_chat','anthropic_messages','ollama'):
            out=self.root/provider
            r=llm_setup.setup_generation(provider,'user-selected',out,transport=self.send)
            self.assertEqual(r['generation_requests'],0)
            self.assertEqual(r['http_requests'],0)
            self.assertEqual(r['secrets_read'],0)
            self.assertEqual(r['status']=='needs_configuration',provider=='ollama')
            before=(out/'model.json').read_bytes()
            with self.assertRaisesRegex(RagError,'output_exists'):
                llm_setup.setup_generation(provider,'new',out,transport=self.send)
            self.assertEqual(before,(out/'model.json').read_bytes())
        self.assertFalse(self.calls)

    def test_missing_mask_and_invalid_options(self):
        out=self.root/'bundle'
        with self.assertRaisesRegex(RagError,'local_model_not_identified'):
            llm_setup.setup_generation('ollama','missing',out,inspect_local=True,transport=self.send)
        self.assertFalse(out.exists())
        with self.assertRaises(ValidationError):
            llm_setup.setup_generation('openai_chat','chosen',out,key_env='contains spaces')
        with self.assertRaises(ValidationError):
            llm_setup.local_models('https://example.org',transport=self.send)
        with self.assertRaises(RagError):
            llm_setup.setup_generation('openai_chat','chosen',out,inspect_local=True,transport=self.send)
        self.assertEqual(len(self.calls),1)
        models=llm_setup.local_models(transport=self.send)
        self.assertEqual(models['models'],[{'model':'qwen3:4b','digest':self.digest}])

    def test_legacy_bundled_and_custom_spec(self):
        spec=llm_setup.sample('handbook-qwen-spec.json')
        sp=self.root/'spec.json';out=self.root/'model.json'
        write_json(sp,spec)
        with self.assertRaisesRegex(RagError,'handbook_digest_mismatch'):
            llm_setup.configure(sp,out,True,transport=self.send)
        self.assertFalse(out.exists())
        spec['profiles']['local']['origin']['hf_id']='user/asserted-model'
        write_json(sp,spec)
        result=llm_setup.configure(sp,out,True,transport=self.send)
        self.assertEqual(result['inspection'][0]['origin'],'user_asserted')
