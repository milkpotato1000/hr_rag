"""P029 actual core/HTTP boundary tests. Only synthetic documents and injected HTTP."""
import copy,contextlib,http.client,io,json,os,socket,tempfile,threading,time,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from rag_package.workspace import init
from rag_package.ui_server import create_server
from rag_package.ui_registry import Registry,atomic_json
from rag_package.ui_jobs import Jobs
from rag_package.storage import RagError,read_json
from rag_package.connectors.drive_config import preview_memory
from rag_package.connectors.google_drive import pull_memory
from test_drive import FakeDrive,meta,TOKEN,RESOURCE

class UITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.ws=self.root/'workspace';init(self.ws)
        self.connect=socket.socket.connect;self.dns=socket.getaddrinfo
        def connect(sock,address):
            if address[0]!='127.0.0.1':raise AssertionError('external network forbidden')
            return self.connect(sock,address)
        def dns(host,*args,**kwargs):
            if host!='127.0.0.1':raise AssertionError('external DNS forbidden')
            return self.dns(host,*args,**kwargs)
        self.patches=[patch.object(socket.socket,'connect',connect),patch.object(socket,'getaddrinfo',dns)]
        for p in self.patches:p.start()
        self.servers=[]
    def tearDown(self):
        for server,thread in self.servers:server.shutdown();server.server_close();thread.join(timeout=3)
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def server(self,**kwargs):
        s=create_server(self.ws,[self.ws/'llm-local.json',self.ws/'llm-api.json'],self.ws/'sources.json',[self.ws/'drive-token-env.json'],port=0,**kwargs);t=threading.Thread(target=s.serve_forever,daemon=True);t.start();self.servers.append((s,t));return s
    def req(self,s,path,method='GET',value=None,headers=None,raw=None):
        h={'X-Rag-Session':s.ui.token,'Origin':s.origin};h.update(headers or {})
        if value is not None:raw=json.dumps(value).encode();h['Content-Type']='application/json'
        c=http.client.HTTPConnection('127.0.0.1',s.server_port,timeout=3);c.request(method,path,body=raw,headers=h);resp=c.getresponse();body=resp.read();result=(resp.status,dict(resp.getheaders()),body);c.close();return result
    def json(self,s,path,**kwargs):
        status,headers,body=self.req(s,path,**kwargs);return status,json.loads(body)
    def submit(self,s,kind,**data):
        status,r=self.json(s,'/api/jobs',method='POST',value={'kind':kind,'request_id':str(uuid.uuid4()),**data});self.assertEqual(status,202,r)
        ident=r['data']['id'];deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            _,r=self.json(s,'/api/jobs/'+ident)
            if r['data']['status'] not in ('queued','running'):return r['data']
            time.sleep(.01)
        self.fail('job timeout')
    def bootstrap(self,s):return self.json(s,'/api/bootstrap')[1]['data']
    def snapshot(self,s):
        b=self.bootstrap(s);r=self.submit(s,'snapshot',input_ids=[x['id'] for x in b['inputs']]);self.assertEqual(r['status'],'completed',r);return r['artifact_ids'][0]
    def build(self,s,snapshot_id,method='fixed',llm=None):
        llm=llm or self.bootstrap(s)['configs'][0]['id'];r=self.submit(s,'build',snapshot_id=snapshot_id,chunking={'method':method,'size_chars':100,'overlap_chars':20},retrieval={'method':'bm25','top_k':5,'context_budget_chars':4000},llm_config_id=llm);self.assertEqual(r['status'],'completed',r);return r['artifact_ids'][0]
    def test_core_flow_three_chunks_pages_preview_compare(self):
        s=self.server();snapshot=self.snapshot(s)
        for method in ('fixed','recursive','structure'):
            build=self.build(s,snapshot,method);_,chunks=self.json(s,'/api/artifacts/'+build+'/chunks?limit=100');items=chunks['data']['items'];self.assertTrue(items)
            c=items[0];page=c['pages'][0];_,value=self.json(s,f'/api/artifacts/{build}/pages?document_id={c["document_id"]}&page={page["page"]}&offset={page["page_start"]}&limit=100')
            self.assertTrue(value['data']['text'].startswith(c['text'][:10]))
            r=self.submit(s,'ask',build_id=build,llm_config_id=self.bootstrap(s)['configs'][0]['id'],question='생일 휴가',top_k=5,context_budget_chars=100)
            self.assertFalse(r['dispatch_attempted']);_,a=self.json(s,'/api/artifacts/'+r['artifact_ids'][0]);self.assertEqual(a['data']['result']['status'],'preview');self.assertTrue(a['data']['result']['excluded'])
        configs=self.bootstrap(s)['configs'];variants=[{'label':str(n),'chunking':{'method':'fixed','size_chars':100,'overlap_chars':20},'retrieval':{'method':'bm25','top_k':5,'context_budget_chars':4000},'llm_config_id':c['id']} for n,c in enumerate(configs)]
        r=self.submit(s,'compare',snapshot_id=snapshot,variants=variants,questions=[{'id':'q1','question':'생일 휴가'},{'id':'q2','question':'zzzzzzz'}]);_,a=self.json(s,'/api/artifacts/'+r['artifact_ids'][0]);self.assertEqual(len(a['data']['result']['rows']),4);self.assertIn('llm',a['data']['result']['configs'][1]['changed_axes_vs_first']);self.assertEqual(len(a['data']['answer_ids']),4)
        self.assertIsNone(a['data']['result']['metrics']['faithfulness']['value'])
    def test_model_clone_shared_role_export_and_stale(self):
        c=read_json(self.ws/'llm-local.json');c['profiles'][c['roles']['generation']]['think']=True;c['roles']['evaluation']=c['roles']['generation'];atomic_json(self.ws/'llm-local.json',c);s=self.server();base=self.bootstrap(s)['configs'][0]['id']
        value={'base_config_id':base,'model':'user:model','max_output_tokens':100,'temperature':0,'local_identity':{'expected_digest':'a'*64,'hf_id':'Example/Model','source_revision':None,'quantization':'Q4'}}
        status,res=self.json(s,'/api/model-configs',method='POST',value=value);self.assertEqual(status,201,res);new=res['data']['id'];self.assertFalse(res['data']['configuration_required'])
        status,_,body=self.req(s,f'/api/model-configs/{new}/export');self.assertEqual(status,200);saved=json.loads(body);self.assertIs(saved['profiles'][saved['roles']['generation']]['think'],True);self.assertNotEqual(saved['roles']['generation'],saved['roles']['evaluation']);self.assertEqual(saved['profiles'][saved['roles']['evaluation']]['model'],'EXAMPLE_OLLAMA_MODEL');ident=saved['profiles'][saved['roles']['generation']]['identity'];self.assertNotIn('license_url',ident);self.assertEqual(ident['conversion'],'user-configured/unverified')
        for delta in ({'base_url':'https://evil.invalid'},{'api_key_env':'SECRET'},{'model':'EXAMPLE_X'}):
            status,_=self.json(s,'/api/model-configs',method='POST',value={**value,**delta});self.assertEqual(status,400)
        api=self.bootstrap(s)['configs'][1]['id'];status,v=self.json(s,'/api/model-configs',method='POST',value={'base_config_id':api,'model':'user-api','max_output_tokens':100,'temperature':0});self.assertEqual(status,201)
        exported=s.ui.registry.llm(v['data']['id']);p=exported['profiles'][exported['roles']['generation']];self.assertFalse(p['identity']['revision_pinned']);self.assertEqual(p['base_url'],'https://api.openai.com/v1')
        atomic_json(self.ws/'llm-local.json',dict(c,extra=True));status,_=self.json(s,f'/api/model-configs/{base}/export');self.assertEqual(status,409)
    def test_http_origin_token_limits_paths_and_upload(self):
        s=self.server()
        for path in ('/','/app.js','/style.css'):
            status,h,b=self.req(s,path);self.assertEqual(status,200);self.assertEqual(h['Cache-Control'],'no-store');self.assertIn("frame-ancestors 'none'",h['Content-Security-Policy'])
        for headers in ({'Origin':'https://evil.invalid'},{'Host':'evil.invalid'}):self.assertEqual(self.req(s,'/api/bootstrap',headers=headers)[0],403)
        self.assertEqual(self.req(s,'/api/jobs',method='POST',headers={'X-Rag-Session':'bad'},value={})[0],403)
        self.assertEqual(self.req(s,'/api/jobs',method='POST',raw=b'{"kind":1,"kind":2}',headers={'Content-Type':'application/json'})[0],400)
        self.assertEqual(self.req(s,'/../x')[0],400);self.assertEqual(self.req(s,'/api/artifacts/../../x')[0],400)
        self.assertEqual(self.req(s,'/api/jobs',method='POST',raw=b'',headers={'Content-Type':'application/json','Content-Length':'20000'})[0],413)
        self.assertEqual(self.req(s,'/api/jobs',method='POST',raw=b'{}',headers={'Content-Type':'application/json','Transfer-Encoding':'chunked'})[0],400)
        h={'Content-Type':'application/octet-stream','X-File-Name':'..%2F%3Cscript%3Ex%3C%2Fscript%3E.txt'}
        status,r=self.json(s,'/api/uploads/txt',method='POST',raw=b'<script>alert(1)</script> synthetic',headers=h);self.assertEqual(status,201);self.assertEqual(r['data']['status'],'uploaded_not_parsed')
        for body in (b'',b'\xff'):
            self.assertIn(self.req(s,'/api/uploads/txt',method='POST',raw=body,headers=h)[0],(400,413))
        r=self.submit(s,'snapshot',input_ids=[r['data']['input_id']]);snap=r['artifact_ids'][0];status,a=self.json(s,'/api/artifacts/'+snap);doc=a['data']['documents'][0]
        self.assertEqual(self.req(s,f'/api/artifacts/{snap}/pages?document_id={doc["document_id"]}&limit=8001')[0],400)
        status,headers,body=self.req(s,f'/api/artifacts/{snap}/original?document_id={doc["document_id"]}');self.assertEqual(status,200);self.assertIn('attachment',headers['Content-Disposition']);self.assertIn(b'<script>',body)
    def test_drive_memory_preview_pull_and_no_url_storage(self):
        fake=FakeDrive();s=self.server(allow_drive=True,drive_transport=fake,env_resolver=lambda _:TOKEN);drive=self.bootstrap(s)['drive_configs'][0]['id'];url='https://drive.google.com/file/d/example_file_id/view?resourcekey='+RESOURCE
        r=self.submit(s,'drive_preview',drive_config_id=drive,url=url);self.assertFalse(r['dispatch_attempted']);self.assertEqual(len(fake.calls),0)
        r=self.submit(s,'drive_pull',drive_config_id=drive,url=url);self.assertEqual(r['status'],'completed',r);self.assertEqual(len(fake.calls),3);self.assertEqual(r['execution_kind'],'test_fixture')
        for p in (self.ws/'.rag-runs/ui').rglob('*.json'):
            t=p.read_text();self.assertNotIn(RESOURCE,t);self.assertNotIn(TOKEN,t);self.assertNotIn(url,t)
        with self.assertRaises(RagError):preview_memory({'schema_version':1,'connector':'google_drive','url':'https://drive.google.com.evil/file/d/a','auth':{'mode':'access_token_env','env':'FAKE'}})
    def test_duplicate_busy_restart_and_write_failure(self):
        s=self.server();inputs=[x['id'] for x in self.bootstrap(s)['inputs']];value={'request_id':str(uuid.uuid4()),'kind':'snapshot','input_ids':inputs};entered=threading.Event();release=threading.Event()
        from rag_package.documents import snapshot as actual
        def slow(*a,**kw):entered.set();release.wait(3);return actual(*a,**kw)
        with patch('rag_package.ui_jobs.snapshot',slow):
            status,v=self.json(s,'/api/jobs',method='POST',value=value);self.assertEqual(status,202);entered.wait(2)
            self.assertEqual(self.json(s,'/api/jobs',method='POST',value=value)[0],200)
            self.assertEqual(self.json(s,'/api/jobs',method='POST',value={**value,'input_ids':inputs[:1]})[0],409)
            self.assertEqual(self.json(s,'/api/jobs',method='POST',value={**value,'request_id':str(uuid.uuid4())})[0],429);release.set();s.ui.jobs.thread.join(3)
        prior=v['data']['id'];r=s.ui.jobs.get(prior);r.update(status='running',dispatch_attempted='unknown');s.ui.jobs.persist(r)
        restarted=Jobs(s.ui.registry);self.assertEqual(restarted.get(prior)['status'],'interrupted');self.assertEqual(restarted.submit(value)[0]['id'],prior)
        with patch('rag_package.ui_jobs.atomic_json',side_effect=OSError('SYNTHETIC_PRIVATE_ERROR')):
            self.assertEqual(self.json(s,'/api/jobs',method='POST',value={**value,'request_id':str(uuid.uuid4())})[0],500)
        self.assertIsNone(s.ui.jobs.active)
    def test_fake_answer_invalid_citation_and_dispatch_write_failure(self):
        calls=[]
        def transport(method,url,headers,body,timeout):
            calls.append(method);data=json.loads(body['messages'][-1]['content']);cid=data['contexts'][0]['chunk_id'];return {'model':'fake-model','choices':[{'message':{'role':'assistant','content':json.dumps({'status':'answered','answer':'Synthetic answer','citations':[{'chunk_id':cid}]})},'finish_reason':'stop'}]}
        c=read_json(self.ws/'llm-api.json');p=c['profiles'][c['roles']['generation']];p['model']='fake-model';p['identity'].update(requested_model='fake-model',validation_status='user_configured_unverified');atomic_json(self.ws/'llm-api.json',c)
        s=self.server(allow_model=True,transport=transport,key_resolver=lambda _:TOKEN);snap=self.snapshot(s);api=self.bootstrap(s)['configs'][1]['id'];build=self.build(s,snap,llm=api)
        args={'build_id':build,'llm_config_id':api,'question':'생일 휴가','top_k':5,'context_budget_chars':4000,'execute':True}
        r=self.submit(s,'ask',**args);self.assertTrue(r['dispatch_attempted']);self.assertEqual(len(calls),1);_,a=self.json(s,'/api/artifacts/'+r['artifact_ids'][0]);result=a['data']['result'];self.assertEqual(result['status'],'answered');self.assertEqual(result['answer']['citations'][0]['quote'],result['contexts'][0]['text'])
        with patch('rag_package.rag.write_json',side_effect=OSError('SYNTHETIC_PRIVATE_ERROR')):
            r=self.submit(s,'ask',**args);self.assertEqual(r['status'],'failed');self.assertTrue(r['dispatch_attempted']);self.assertNotIn('SYNTHETIC_PRIVATE_ERROR',json.dumps(r))
        self.assertEqual(len(calls),2)
        args['llm_config_id']=self.bootstrap(s)['configs'][0]['id'];status,r=self.json(s,'/api/jobs',method='POST',value={'request_id':str(uuid.uuid4()),'kind':'ask',**args});self.assertEqual(status,400);self.assertEqual(r['error']['code'],'configuration_required');self.assertEqual(len(calls),2)
    def test_registry_path_symlink_tamper_and_limits(self):
        outside=self.root/'outside.json';outside.write_text('{}')
        with self.assertRaises(RagError):Registry(self.ws,[outside])
        link=self.ws/'linked.json';link.symlink_to(self.ws/'llm-local.json')
        with self.assertRaises(RagError):Registry(self.ws,[link])
        s=self.server();snap=self.snapshot(s);build=self.build(s,snap)
        self.assertEqual(self.req(s,'/api/artifacts/'+build+'/chunks?limit=101')[0],400)
        entry=s.ui.registry.data['artifacts'][build];path=self.ws/entry['path'];(path/'chunks.json').write_text('[]')
        self.assertEqual(self.req(s,'/api/artifacts/'+build)[0],409)
        status,r=self.json(s,'/api/jobs',method='POST',value={'kind':'snapshot','request_id':str(uuid.uuid4()),'input_ids':[{}]});self.assertEqual(status,400)
        self.assertEqual(self.req(s,'/api/uploads/pdf',method='POST',raw=b'',headers={'Content-Length':str(20*1024*1024+1),'Content-Type':'application/octet-stream','X-File-Name':'fake.pdf'})[0],413)
        for _ in range(18):s.ui.registry.upload('txt','synthetic',b'text')
        with self.assertRaises(RagError):s.ui.registry.upload('txt','extra',b'text')
        s.ui.registry.inputs={};bad=self.ws/'bad.txt';bad.write_text('v1');s.ui.registry.inputs['a'*32]={'path':'bad.txt','sha256':'0'*64,'document_id':'bad','title':'bad','format':'txt','synthetic':True}
        with self.assertRaises(RagError):s.ui.registry.freeze_inputs(['a'*32])
    def test_needs_review_invalid_citation_and_completed_job_write_failure(self):
        import pypdf
        writer=pypdf.PdfWriter();writer.add_blank_page(100,100);pdf=io.BytesIO();writer.write(pdf)
        calls=[]
        def invalid(method,url,headers,body,timeout):
            calls.append(method);return {'model':'fake','choices':[{'message':{'role':'assistant','content':json.dumps({'status':'answered','answer':'bad citation','citations':[{'chunk_id':'NOT_IN_CONTEXT'}]})},'finish_reason':'stop'}]}
        c=read_json(self.ws/'llm-api.json');p=c['profiles'][c['roles']['generation']];p['model']='fake';p['identity'].update(requested_model='fake',validation_status='user_configured_unverified');atomic_json(self.ws/'llm-api.json',c)
        s=self.server(allow_model=True,transport=invalid,key_resolver=lambda _:TOKEN)
        inp=s.ui.registry.upload('pdf','scan.pdf',pdf.getvalue());r=self.submit(s,'snapshot',input_ids=[inp['input_id']]);self.assertEqual(r['status'],'needs_review')
        s.ui.registry.inputs.pop(inp['input_id']);snap=self.snapshot(s);api=self.bootstrap(s)['configs'][1]['id'];build=self.build(s,snap,llm=api)
        args={'build_id':build,'llm_config_id':api,'question':'생일 휴가','top_k':5,'context_budget_chars':4000,'execute':True}
        r=self.submit(s,'ask',**args);self.assertEqual(r['status'],'failed');self.assertEqual(r['error']['code'],'invalid_citation');self.assertTrue(r['dispatch_attempted'])
        actual=s.ui.jobs.persist
        def failed_terminal(record):
            if record['status']=='failed' and record['stage']=='finished':raise OSError('SYNTHETIC_WRITE')
            return actual(record)
        with patch.object(s.ui.jobs,'persist',failed_terminal):
            r=self.submit(s,'ask',**args);self.assertEqual(r['status'],'failed');self.assertTrue(r['dispatch_attempted']);self.assertNotIn('SYNTHETIC_WRITE',json.dumps(r))
        before=len(calls);args['question']='zzzzzz';r=self.submit(s,'ask',**args);self.assertEqual(r['status'],'completed');self.assertFalse(r['dispatch_attempted']);self.assertEqual(len(calls),before)
    def test_real_restart_exports_and_execution_flags(self):
        s=self.server();snap=self.snapshot(s);build=self.build(s,snap);b=self.bootstrap(s)
        status,r=self.json(s,'/api/jobs',method='POST',value={'kind':'ask','request_id':str(uuid.uuid4()),'build_id':build,'llm_config_id':b['configs'][0]['id'],'question':'생일','top_k':5,'context_budget_chars':1000,'execute':True});self.assertEqual(status,403)
        status,r=self.json(s,'/api/jobs',method='POST',value={'kind':'drive_pull','request_id':str(uuid.uuid4()),'drive_config_id':b['drive_configs'][0]['id'],'url':'https://drive.google.com/file/d/a'});self.assertEqual(status,403)
        value={'base_config_id':b['configs'][1]['id'],'model':'new-api','max_output_tokens':100,'temperature':0}
        _,created=self.json(s,'/api/model-configs',method='POST',value=value);config_id=created['data']['id'];record=list(s.ui.jobs.records.values())[0]
        s.shutdown();s.server_close();self.servers[0][1].join();self.servers=[]
        s2=self.server();self.assertEqual(self.req(s2,'/api/jobs/'+record['id'])[0],200);self.assertEqual(self.req(s2,'/api/artifacts/'+snap)[0],200);self.assertEqual(self.req(s2,'/api/model-configs/'+config_id+'/export')[0],200)
        self.assertEqual(self.req(s2,'/api/model-configs/'+config_id+'/export',headers={'X-Rag-Session':'old'})[0],403)
    def test_candidate_excluded_provenance_non_bmp(self):
        s=self.server();text='생일 😀 휴가 자격 '+('조건 😀 일정 '+ '가나다라마바사 '*8)*5
        inp=s.ui.registry.upload('txt','emoji.txt',text.encode());snap=self.submit(s,'snapshot',input_ids=[inp['input_id']])['artifact_ids'][0];build=self.build(s,snap)
        r=self.submit(s,'ask',build_id=build,llm_config_id=self.bootstrap(s)['configs'][0]['id'],question='생일 휴가 조건',top_k=10,context_budget_chars=100)
        _,a=self.json(s,'/api/artifacts/'+r['artifact_ids'][0]);data=a['data'];self.assertTrue(data['result']['excluded']);lookup={x['chunk_id']:x for x in data['candidate_chunks']}
        for row in data['result']['candidates']+data['result']['excluded']:
            c=lookup[row['chunk_id']];self.assertEqual(c['text'],text[c['start']:c['end']]);self.assertEqual(c['end']-c['start'],len(c['text']))
        self.assertTrue(any(len(c['text'].encode('utf-16-le'))//2>c['end']-c['start'] for c in lookup.values()))
