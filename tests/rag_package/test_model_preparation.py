"""P031 independent source-byte/identity/failure/configuration checks."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from rag_package import model_catalog as catalog, model_preparation as prep, llm_setup
from rag_package.storage import write_json, read_json, fingerprint, RagError
from rag_package.workspace import doctor
from rag_package.llm.config import ValidationError

E5='intfloat/multilingual-e5-small';BGE='BAAI/bge-m3'


def fixture(root,model=E5):
    root=Path(root);src=root/'source';src.mkdir(parents=True)
    payloads={n:b'tiny fixture '+n.encode() for n in catalog.recipe(model)}
    if catalog.RECIPES[model][1]=='embedding':
        payloads['config.json']=json.dumps({'hidden_size':384 if model==E5 else 1024}).encode()
        payloads['modules.json']=json.dumps([{'type':'sentence_transformers.models.Transformer','path':''},{'type':'sentence_transformers.models.Pooling','path':'1_Pooling'}]).encode()
        payloads['1_Pooling/config.json']=json.dumps({'pooling_mode':'mean' if model==E5 else 'cls'}).encode()
    else:payloads['config.json']=json.dumps({'architectures':['XLMRobertaForSequenceClassification'],'model_type':'xlm-roberta','num_labels':1}).encode()
    for n in payloads:
        if n.endswith('.json') and n not in ('config.json','modules.json','1_Pooling/config.json'):payloads[n]=b'{}'
    rows=[]
    for n,data in payloads.items():
        p=src/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        rows.append({'path':n,'size':len(data),'git_blob_oid':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\x00'+data).hexdigest(),'lfs_sha256':hashlib.sha256(data).hexdigest() if n.endswith(('.safetensors','.bin','.model')) else None})
    fetched={'revision':'a'*40,'files':rows,'observed_at':'2026-11-28'}
    catalog.plan(model,catalog.RECIPES[model][1],root/'plan',revision='test-ref',fetch_metadata=True,metadata_backend=lambda _:fetched)
    return src,root/'plan'


def spec(provider='ollama'):
    p={'provider':provider,'base_url':'http://127.0.0.1:11434' if provider=='ollama' else 'https://example.com/v1','model':'example-model','max_output_tokens':256,'timeout_seconds':10,'response_mode':'json_object'}
    if provider=='ollama':p['origin']={'hf_id':'user/model','source_revision':None,'conversion':'user supplied','quantization':'unknown'}
    else:p.update(api_key_env='EXAMPLE_API_KEY',revision_pinned=False,revision=None)
    return {'schema_version':1,'profiles':{'chosen':p},'roles':{'generation':'chosen','evaluation':'chosen','chunking':'chosen'}}


class PreparationTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
    def tearDown(self):self.tmp.cleanup()
    def test_catalog_pinned_and_unresolved_preview_no_calls(self):
        with patch('socket.socket.connect',side_effect=AssertionError('network')):
            c=catalog.catalog();self.assertEqual(len(c['models']),4)
            for i,m in enumerate(c['models']):
                p=catalog.plan(m['model_id'],m['role'],self.root/str(i));self.assertEqual(p['revision'],catalog.metadata(m['model_id'])['revision'])
                self.assertEqual(p['total_bytes'],sum(x['size'] for x in p['files']))
            p=catalog.plan(E5,'embedding',self.root/'unresolved',revision='main');self.assertEqual(p['status'],'unresolved_preview')
            with self.assertRaises(RagError):prep.prepare(self.root/'unresolved',self.root/'out',execute_download=True)
    def test_incomplete_metadata_does_not_fall_back_to_packaged_ready(self):
        for i,value in enumerate(({},None,{'revision':'a'*40},[])):
            # A backend returning no result must not silently become a packaged plan.
            with self.assertRaises(RagError):catalog.plan(E5,'embedding',self.root/str(i),fetch_metadata=True,metadata_backend=lambda _,value=value:value)
            self.assertFalse((self.root/str(i)).exists())

    def test_plan_semantic_tamper_even_with_new_hash(self):
        p=catalog.make_plan(E5,'embedding')
        for key,value in [('role','reranker'),('conversion','custom-python'),('total_bytes',2),('revision','b'*40),('files',p['files'][:-1]),('schema_version',True)]:
            q=copy.deepcopy(p);q[key]=value;q['plan_sha256']=fingerprint({k:v for k,v in q.items() if k!='plan_sha256'})
            with self.subTest(key=key),self.assertRaises(RagError):catalog.validate(q)
        for name in ('../escape','/absolute','a//b','config.json'):
            q=copy.deepcopy(p);q['files'].append(dict(q['files'][0],path=name));q['plan_sha256']=fingerprint({k:v for k,v in q.items() if k!='plan_sha256'})
            with self.assertRaises(RagError):catalog.validate(q)
    def test_import_hashes_relative_profile_and_no_inference(self):
        src,plan=fixture(self.root)
        before={p.relative_to(src).as_posix():p.read_bytes() for p in src.rglob('*') if p.is_file()}
        with patch('socket.socket.connect',side_effect=AssertionError('network')),patch('rag_package.embedding.encode',side_effect=AssertionError('inference')):
            r=prep.prepare(plan,self.root/'export',source=src);self.assertEqual(r['status'],'ready',r)
            ck=prep.model_check(self.root/'export/profile.json');self.assertEqual(ck['inference'],'unverified')
        p=read_json(self.root/'export/profile.json');self.assertEqual(p['local_path'],'model');self.assertEqual(p['max_input_tokens'],512)
        self.assertIn('source-provenance.json',p['file_manifest'])
        for n,data in before.items():self.assertEqual((src/n).read_bytes(),data)
        self.assertEqual(r['execution_kind'],'test_fixture')
        for n,h in p['file_manifest'].items():self.assertEqual(hashlib.sha256((self.root/'export/model'/n).read_bytes()).hexdigest(),h)
    def test_download_fixture_uses_same_core(self):
        src,plan=fixture(self.root);seen=[]
        def download(p):
            import shutil
            seen.append(p);shutil.copytree(src,p['destination'],dirs_exist_ok=True)
        r=prep.prepare(plan,self.root/'out',execute_download=True,download_backend=download)
        self.assertEqual(r['status'],'ready',r);self.assertEqual(len(seen),1);self.assertEqual(seen[0]['plan']['revision'],'a'*40)
        self.assertEqual(r['work']['download']['workers_started'],0);self.assertEqual(r['work']['download']['fixture_calls'],1)
    def test_hash_size_symlink_and_partial_download_failures(self):
        for kind in ('hash','size','symlink','partial'):
            base=self.root/kind;src,plan=fixture(base)
            if kind=='hash':(src/'config.json').write_bytes(b'x'*(src/'config.json').stat().st_size)
            if kind=='size':(src/'config.json').write_bytes(b'x')
            if kind=='symlink':(src/'model.safetensors').unlink();(src/'model.safetensors').symlink_to(src/'tokenizer.json')
            if kind=='partial':(src/'model.safetensors').unlink()
            r=prep.prepare(plan,base/'out',source=src);self.assertEqual(r['status'],'failed',r);self.assertFalse((base/'out').exists());self.assertTrue((base/'out.preparation.json').exists())
    def test_disk_and_confirmation_preflight(self):
        src,plan=fixture(self.root)
        r=prep.prepare(plan,self.root/'out');self.assertEqual(r['status'],'preview');self.assertFalse((self.root/'out').exists())
        with self.assertRaises(RagError):prep.prepare(plan,self.root/'out',source=src,disk_free=lambda _:0)
        b=self.root/'bge';bs,bp=fixture(b,BGE)
        r=prep.prepare(bp,b/'out',execute_download=True,download_backend=lambda _:self.fail('download'));self.assertEqual(r['reason'],'conversion_confirmation_required')
    def test_publication_and_journal_failure_do_not_expose_failed_ready(self):
        for kind in ('initial','intent','publish','ack'):
            base=self.root/kind;src,plan=fixture(base)
            def persist(path,value):
                if (kind=='initial' and value['phase']=='preflight') or (kind=='intent' and value['phase']=='publication_intent') or (kind=='ack' and value['phase']=='published'):raise OSError('injected')
                prep.atomic_json(path,value)
            def publish(a,b):
                if kind=='publish':raise OSError('injected')
                prep.exclusive_rename(a,b)
            r=prep.prepare(plan,base/'out',source=src,persist=persist,publish=publish)
            self.assertEqual(r['status'],'ready' if kind=='ack' else 'failed',r);self.assertEqual((base/'out/profile.json').exists(),kind=='ack')
            if kind=='ack':self.assertEqual(r['diagnostic_status'],'ack_write_failed')
    def test_parent_killed_preserves_durable_in_progress_and_no_auto_resume(self):
        import subprocess,sys,time
        src,plan=fixture(self.root)
        code="from rag_package.model_preparation import prepare; import time; prepare(%r,%r,source=%r,persist=lambda *a:time.sleep(30))" % (str(plan),str(self.root/'out'),str(src))
        proc=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            end=time.monotonic()+5
            while time.monotonic()<end:
                if (self.root/'out.preparation.json').exists():break
                time.sleep(.02)
            record=read_json(self.root/'out.preparation.json');self.assertEqual(record['status'],'in_progress')
            proc.kill();proc.wait(timeout=5);self.assertIsNotNone(proc.returncode)
            self.assertFalse((self.root/'out').exists());self.assertTrue(list(self.root.glob('.out-preparing-*')))
            with self.assertRaises(RagError):prep.prepare(plan,self.root/'out',source=src)
            self.assertEqual(read_json(self.root/'out.preparation.json'),record)
        finally:
            if proc.poll() is None:proc.kill();proc.wait()

    def test_interrupt_and_missing_sdk_accounting(self):
        src,plan=fixture(self.root)
        r=prep.prepare(plan,self.root/'out',execute_download=True,download_backend=lambda _:(_ for _ in ()).throw(KeyboardInterrupt()))
        self.assertEqual(r['status'],'interrupted');self.assertFalse((self.root/'out').exists())
        with patch('rag_package.model_process.dependency',side_effect=RagError('preparation_dependency_missing','test')):
            r=prep.prepare(plan,self.root/'out2',execute_download=True)
        self.assertEqual(r['status'],'failed');self.assertEqual(r['work']['download']['workers_started'],0)
    def test_llm_offline_local_api_and_mixed_strict(self):
        for provider in ('ollama','openai_chat','anthropic_messages'):
            sp=self.root/(provider+'.json');write_json(sp,spec(provider))
            with patch('socket.socket.connect',side_effect=AssertionError('network')),patch('os.getenv',side_effect=AssertionError('key')):
                r=llm_setup.configure(sp,self.root/(provider+'-out.json'))
            cfg=read_json(self.root/(provider+'-out.json'));self.assertEqual(cfg['schema_version'],2);self.assertEqual(r['http_requests'],0)
            if provider=='ollama':self.assertEqual(cfg['profiles']['chosen']['identity']['expected_digest'],'0'*64)
            with self.assertRaises(RagError):llm_setup.configure(sp,self.root/(provider+'-out.json'))
        value=spec();value['profiles']['api']=spec('openai_chat')['profiles']['chosen'];value['roles']['chunking']='api';write_json(self.root/'mixed.json',value)
        llm_setup.configure(self.root/'mixed.json',self.root/'mixed-out.json')
        for change in ('secret','unknown_role','bool'):
            v=spec()
            if change=='secret':v['profiles']['chosen']['api_key']='NEVER_A_KEY'
            elif change=='unknown_role':v['roles']['chunking']='missing'
            else:v['profiles']['chosen']['max_output_tokens']=True
            write_json(self.root/'invalid.json',v)
            with self.assertRaises(ValidationError):llm_setup.configure(self.root/'invalid.json',self.root/'invalid-out.json')
    def test_local_inspection_deduplicated_identity_only(self):
        v=spec();v['profiles']['second']=copy.deepcopy(v['profiles']['chosen']);v['roles']['chunking']='second';write_json(self.root/'spec.json',v);calls=[]
        def send(method,url,headers,body,timeout):
            calls.append((method,url,body,timeout))
            if url.endswith('/api/tags'):return {'models':[{'name':'example-model','digest':'1'*64}]}
            return {'model_info':{'general.architecture':'test','general.parameter_count':42},'license':'DO NOT DUMP','template':'DO NOT DUMP'}
        r=llm_setup.configure(self.root/'spec.json',self.root/'out.json',True,transport=send)
        self.assertEqual(len(calls),2);self.assertEqual([x[0] for x in calls],['GET','POST']);self.assertEqual(r['generation_requests'],0)
        self.assertNotIn('DO NOT DUMP',json.dumps(r));self.assertTrue(all(x['origin']=='user_asserted' for x in r['inspection']))
        self.assertEqual(read_json(self.root/'out.json')['profiles']['chosen']['identity']['expected_digest'],'1'*64)
    def test_owned_worker_timeout_rss_pressure_and_exit_accounting(self):
        from rag_package.model_process import run_worker
        class Process:
            returncode=None
            def __init__(self):self.pid=42;self.killed=False;self.waited=False
            def poll(self):return self.returncode
            def kill(self):self.killed=True;self.returncode=-9
            def wait(self):self.waited=True;return self.returncode
        for kind in ('timeout','rss','pressure','unavailable'):
            d=self.root/kind;d.mkdir();proc=Process();obs={};samples=[0]
            def monitor():
                samples[0]+=1
                if kind=='pressure' and samples[0]>1:raise RagError('memory_pressure','test')
                if kind=='unavailable':raise RagError('memory_observation_unavailable','test')
                return {'pressure':'normal'}
            with patch('rag_package.model_process.dependency'),patch('rag_package.model_process.subprocess.Popen',return_value=proc),self.assertRaises(RagError):
                run_worker({'operation':'conversion'},d,timeout=0 if kind=='timeout' else 10,observation=obs,monitor=monitor,rss_reader=lambda _:4*1024**3)
            self.assertEqual(obs['workers_started'],0 if kind=='unavailable' else 1)
            if kind!='unavailable':self.assertTrue(proc.killed and proc.waited and obs['worker_exited'])
    def test_linux_measurement_semantics(self):
        from rag_package.model_process import pressure,rss
        with patch('rag_package.model_process.sys.platform','linux'),patch('pathlib.Path.read_text',return_value='MemAvailable: 2097152 kB\nMemTotal: 8388608 kB\n'):
            self.assertEqual(pressure()['available_bytes'],2*1024**3)
        with patch('rag_package.model_process.sys.platform','linux'),patch('pathlib.Path.read_text',return_value='VmRSS: 1234 kB\n'):
            self.assertEqual(rss(1),1234*1024)
        with patch('rag_package.model_process.sys.platform','linux'),patch('pathlib.Path.read_text',return_value='MemAvailable: 10 kB\n'),self.assertRaises(RagError):pressure()
    def test_sidecar_ui_provenance_and_change_detection(self):
        from rag_package.ui_registry import preparation_summary
        from rag_package.embedding import read_profile
        src,plan=fixture(self.root);prep.prepare(plan,self.root/'out',source=src);profile=read_profile(self.root/'out/profile.json')
        summary=preparation_summary(profile);self.assertEqual(summary['status'],'preparation_record_verified');self.assertEqual(summary['execution_kind'],'test_fixture')
        (self.root/'out/model/source-provenance.json').write_text('{}')
        self.assertEqual(preparation_summary(profile)['status'],'preparation_record_invalid')
        with self.assertRaises(RagError):prep.model_check(self.root/'out/profile.json')
    def test_real_loopback_inspection_and_failure_no_output(self):
        import threading
        from http.server import BaseHTTPRequestHandler,HTTPServer
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_GET(self):
                requests.append(('GET',self.path));body=json.dumps({'models':[{'name':'example-model','digest':'f'*64}]}).encode();self.send_response(200);self.end_headers();self.wfile.write(body)
            def do_POST(self):
                requests.append(('POST',self.path));self.rfile.read(int(self.headers['Content-Length']));self.send_response(200);self.end_headers();self.wfile.write(b'{"model_info":{"general.architecture":"tiny"}}')
        server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            value=spec();value['profiles']['chosen']['base_url']='http://127.0.0.1:'+str(server.server_port);write_json(self.root/'spec.json',value)
            result=llm_setup.configure(self.root/'spec.json',self.root/'out.json',True)
            self.assertEqual(requests,[('GET','/api/tags'),('POST','/api/show')]);self.assertEqual(result['http_requests'],2)
            with self.assertRaises(RagError) as err:llm_setup.configure(self.root/'spec.json',self.root/'bad.json',True,transport=lambda *a:{'models':[]})
            self.assertEqual(err.exception.requests,1);self.assertFalse((self.root/'bad.json').exists())
        finally:server.shutdown();server.server_close();thread.join()

    def test_doctor_role_checks_preserve_drive_dependency_status(self):
        from rag_package.workspace import dependency
        before,_=doctor()
        sp=self.root/'spec.json';write_json(sp,spec());llm_setup.configure(sp,self.root/'llm.json')
        src,plan=fixture(self.root/'source-fixture');prep.prepare(plan,self.root/'prepared',source=src)
        after,_=doctor(llm_config=self.root/'llm.json',embedding_config=self.root/'prepared/profile.json')
        self.assertEqual(before['optional_dependencies']['drive'],after['optional_dependencies']['drive'])

    def test_doctor_chunking_role_and_no_file_hash_or_network(self):
        sp=self.root/'spec.json';write_json(sp,spec());llm_setup.configure(sp,self.root/'llm.json')
        cfg=read_json(self.root/'llm.json');cfg['profiles']['ready']=copy.deepcopy(cfg['profiles']['chosen']);cfg['profiles']['ready']['identity'].update(expected_digest='a'*64,validation_status='user_configured_unverified');cfg['roles'].update(generation='ready',evaluation='ready');write_json(self.root/'llm.json',cfg)
        with patch('socket.socket.connect',side_effect=AssertionError('network')):
            r,code=doctor(llm_config=self.root/'llm.json')
        self.assertEqual(code,3);self.assertEqual(r['role_configs']['llm']['roles']['chunking'],'example_requires_configuration')
        src,plan=fixture(self.root/'profile');prep.prepare(plan,self.root/'prepared',source=src)
        with patch('rag_package.embedding.check_files',side_effect=AssertionError('no full hash')):
            r,code=doctor(embedding_config=self.root/'prepared/profile.json')
        self.assertEqual(code,0);self.assertEqual(r['role_configs']['embedding']['status'],'configured_unverified')

if __name__=='__main__':unittest.main()
