"""P027 offline Drive/auth tests; real credentials and Google are never accessed."""
import contextlib,copy,hashlib,io,json,logging,os,socket,stat,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading
from rag_package.connectors.drive_config import link,config,preview,SCOPE
from rag_package.connectors.google_drive import pull,metadata
from rag_package.connectors.drive_http import bounded_get
from rag_package import drive_auth as auth
from rag_package.storage import RagError,read_json,write_json,fingerprint
from rag_package.documents import load_snapshot
from rag_package.retrieval import build
from rag_package.rag import ask
from rag_package.__main__ import main
from test_llm import config as llm_config

ROOT=Path(__file__).resolve().parents[2]
TOKEN='SYNTHETIC_TOKEN_SECRET_P027'
RESOURCE='SYNTHETIC_RESOURCE_SECRET_P027'
FID='example_file_id'


def meta(data=b'leave eligibility',mime='text/plain',name='example.txt'):
    return {'id':FID,'name':name,'mimeType':mime,'version':'12','modifiedTime':'2026-11-27T01:02:03.000Z','trashed':False,'capabilities':{'canDownload':True},'size':str(len(data)),'sha256Checksum':hashlib.sha256(data).hexdigest(),'md5Checksum':hashlib.md5(data).hexdigest()}

class FakeDrive:
    def __init__(self,data=b'leave eligibility',before=None,after=None,fail=None):
        self.data=data;self.before=before or meta(data);self.after=after or copy.deepcopy(self.before);self.calls=[];self.fail=fail
    def __call__(self,url,headers,limit,deadline):
        self.calls.append((url,headers,limit))
        if self.fail:raise self.fail
        if len(self.calls)==1:return json.dumps(self.before).encode()
        if len(self.calls)==2:return self.data
        return json.dumps(self.after).encode()

class Creds:
    def __init__(self,info,valid=True):self.info=info;self.valid=valid;self.token=TOKEN
    def has_scopes(self,scopes):return self.info['scopes']==scopes
    def to_json(self):return json.dumps(dict(self.info,token=self.token))

class FakeAuth:
    def __init__(self,info,valid=True,fail=False):self.info=info;self.valid=valid;self.fail=fail;self.refreshes=0
    def login(self,client):return Creds(self.info)
    def load(self,info):return Creds(info,self.valid)
    def refresh(self,creds):
        self.refreshes+=1
        if self.fail:raise RuntimeError(TOKEN)
        creds.valid=True;return 1

class DriveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.d=Path(self.temp.name).resolve()
        self.connect=patch.object(socket.socket,'connect',side_effect=AssertionError('external network forbidden'));self.connect.start()
        self.dns=patch.object(socket,'getaddrinfo',side_effect=AssertionError('external DNS forbidden'));self.dns.start()
        self.private=self.d/'private';self.private.mkdir(mode=0o700)
    def tearDown(self):self.dns.stop();self.connect.stop();self.temp.cleanup()
    def cfg(self,mode='access_token_env'):
        c={'schema_version':1,'connector':'google_drive','url':f'https://drive.google.com/file/d/{FID}/view?usp=sharing&resourcekey={RESOURCE}',
           'auth':{'mode':mode,'env':'P027_FAKE_TOKEN'} if mode=='access_token_env' else {'mode':mode,'credentials_file':str(self.private/'credentials.json')}}
        write_json(self.d/'drive.json',c);return self.d/'drive.json'
    def info(self):return {'type':'authorized_user','token':TOKEN,'refresh_token':'FAKE_REFRESH_SECRET_P027','client_id':'fake-client','client_secret':'FAKE_CLIENT_SECRET_P027','token_uri':auth.TOKEN_URI,'scopes':[SCOPE],'expiry':'2099-01-01T00:00:00Z'}
    def protected(self,path,value):write_json(path,value);path.chmod(0o600)
    def no_secrets(self,value):
        text=value if isinstance(value,str) else json.dumps(value)
        for secret in (TOKEN,RESOURCE,'FAKE_REFRESH_SECRET_P027','FAKE_CLIENT_SECRET_P027'):self.assertNotIn(secret,text)

    def test_strict_links_and_offline_preview(self):
        valid=['https://drive.google.com/file/d/a/view','https://drive.google.com/file/d/a','https://drive.google.com/open?id=a','https://docs.google.com/document/d/a/edit?tab=t.0']
        for u in valid:self.assertEqual(link(u),(u.split('/d/')[-1].split('/')[0] if '/d/' in u else 'a',None))
        invalid=['http://drive.google.com/file/d/a','https://drive.google.com.evil/file/d/a','https://drive.google.com:443/file/d/a','https://user@drive.google.com/file/d/a','https://drive.google.com/drive/folders/a','https://docs.google.com/spreadsheets/d/a/edit','https://drive.google.com/open?id=a&id=b','https://drive.google.com/file/d/a?resourcekey=x&resourcekey=y','https://drive.google.com/file/d/a#x','https://drive.google.com/file/d/../a','https://drive.google.com/open?id=%0a','https://drive.google.com/file/d/a?id=b']
        for u in invalid:
            with self.subTest(url=u),self.assertRaises(RagError):link(u)
        path=self.cfg()
        with patch('os.environ.get',side_effect=AssertionError('secret lookup')),patch('rag_package.drive_auth.sdk',side_effect=AssertionError('SDK import')),patch('rag_package.connectors.google_drive.acquire',side_effect=AssertionError('auth')):
            r=preview(path);r2=pull(path,self.d/'unused')
        self.assertFalse(r['remote_access_verified']);self.assertEqual(r2['requests'],0);self.assertFalse((self.d/'unused').exists());self.no_secrets(r)
        for key,value in [('token',TOKEN),('extra',True)]:
            c=read_json(path);c[key]=value;write_json(self.d/'bad.json',c)
            with self.assertRaises(RagError):config(self.d/'bad.json')

    def test_blob_resource_key_origin_and_pipeline(self):
        p=self.cfg();fake=FakeDrive()
        r=pull(p,self.d/'pulled',execute=True,transport=fake,env_resolver=lambda _:TOKEN)
        self.assertEqual(r['status'],'ready');self.assertEqual(r['execution_kind'],'test_fixture');self.assertEqual(r['requests'],3)
        self.assertEqual(fake.calls[0][1]['X-Goog-Drive-Resource-Keys'],FID+'/'+RESOURCE)
        self.assertTrue(all(u.startswith('https://www.googleapis.com/drive/v3/files/'+FID) for u,_,_ in fake.calls))
        self.assertTrue(all(RESOURCE not in u and 'usp' not in u for u,_,_ in fake.calls))
        sm,docs=load_snapshot(self.d/'pulled/snapshot');self.assertEqual(docs[0]['origin']['remote_version'],'12')
        self.assertEqual(docs[0]['origin']['downloaded_sha256'],docs[0]['original_sha256']);self.assertEqual(docs[0]['origin']['execution_kind'],'test_fixture')
        self.no_secrets(r)
        for file in (self.d/'pulled').rglob('*'):
            if file.is_file():self.no_secrets(file.read_text())
        write_json(self.d/'llm.json',llm_config('openai_chat','json_object'))
        write_json(self.d/'rag.json',{'schema_version':1,'chunking':{'method':'fixed','size_chars':100,'overlap_chars':0},'retrieval':{'method':'bm25','top_k':2,'context_budget_chars':500},'llm_config':'llm.json'})
        build(self.d/'pulled/snapshot',self.d/'rag.json',self.d/'build')
        a=ask(self.d/'build',self.d/'rag.json','leave',self.d/'answer')
        self.assertEqual(a['status'],'preview');self.assertEqual(a['source_origins'][docs[0]['document_id']],docs[0]['origin'])
        self.assertEqual(a['source_fingerprint'],sm['fingerprint'])

    def test_version_bytes_changes_and_origin_tampering(self):
        p=self.cfg();r1=pull(p,self.d/'a',execute=True,transport=FakeDrive(),env_resolver=lambda _:TOKEN)
        changed=meta();changed['version']='13';r2=pull(p,self.d/'b',execute=True,transport=FakeDrive(before=changed),env_resolver=lambda _:TOKEN)
        r3=pull(p,self.d/'c',execute=True,transport=FakeDrive(b'leave changed'),env_resolver=lambda _:TOKEN)
        self.assertNotEqual(r1['snapshot_fingerprint'],r2['snapshot_fingerprint']);self.assertNotEqual(r1['snapshot_fingerprint'],r3['snapshot_fingerprint'])
        path=self.d/'a/snapshot/manifest.json';m=read_json(path);m['identity']['documents'][0]['origin']['downloaded_sha256']='0'*64;m['fingerprint']=fingerprint(m['identity']);write_json(path,m)
        with self.assertRaises(RagError):load_snapshot(path.parent)

    def test_supported_pdf_markdown_export_and_scan(self):
        from pypdf import PdfWriter
        # Existing public synthetic PDF exercises real parser/export bytes.
        data=(ROOT/'2. Document Chunking/data/source-v4/output/pdf/hr-handbook.pdf').read_bytes()
        p=self.cfg()
        for n,(mime,name,body) in enumerate([('application/pdf','doc.pdf',data),('text/markdown','doc.md',b'# leave\neligibility'),('text/plain','DOC.MD',b'# leave\nconditions'),('application/vnd.google-apps.document','Google Doc',data)]):
            before=meta(body,mime,name)
            if mime.startswith('application/vnd.'):before={k:v for k,v in before.items() if k not in ('size','md5Checksum','sha256Checksum')}
            f=FakeDrive(body,before);r=pull(p,self.d/str(n),execute=True,transport=f,env_resolver=lambda _:TOKEN)
            self.assertEqual(r['status'],'ready')
            _,docs=load_snapshot(self.d/str(n)/'snapshot')
            self.assertEqual(docs[0]['format'],'md' if name.lower().endswith('.md') else 'pdf')
            if mime.startswith('application/vnd.'):
                self.assertIn('/export?mimeType=application%2Fpdf',f.calls[1][0]);self.assertEqual(f.calls[1][2],10_000_000)
        writer=PdfWriter();writer.add_blank_page(100,100);stream=io.BytesIO();writer.write(stream);body=stream.getvalue()
        r=pull(p,self.d/'scan',execute=True,transport=FakeDrive(body,meta(body,'application/pdf','scan.pdf')),env_resolver=lambda _:TOKEN)
        self.assertEqual(r['status'],'needs_review');self.assertTrue(r['snapshot_reasons'])

    def test_metadata_failures_and_three_request_limit(self):
        path=self.cfg()
        for field,value in [('mimeType','application/vnd.google-apps.folder'),('mimeType','application/vnd.google-apps.shortcut'),('mimeType','text/html'),('driveId','shared'),('trashed',True),('capabilities',{'canDownload':False}),('size',str(20*1024*1024+1)),('id','wrong'),('version','bad')]:
            m=meta();m[field]=value;f=FakeDrive(before=m)
            with self.subTest(field=field),self.assertRaises(RagError) as err:pull(path,self.d/(field+'-'+str(len(value)) if isinstance(value,str) else field),execute=True,transport=f,env_resolver=lambda _:TOKEN)
            self.assertEqual(len(f.calls),1);self.assertTrue(err.exception.dispatch_attempted);self.no_secrets(str(err.exception))
        for change in ({'version':'13'},{'modifiedTime':'2026-11-28T00:00:00Z'},{'capabilities':{'canDownload':False}},{'trashed':True},{'mimeType':'text/markdown'},{'size':'2'},{'sha256Checksum':'0'*64}):
            after=meta();after.update(change);f=FakeDrive(after=after)
            with self.assertRaises(RagError) as err:pull(path,self.d/'race',execute=True,transport=f,env_resolver=lambda _:TOKEN)
            self.assertEqual(err.exception.code,'source_changed');self.assertEqual(len(f.calls),3)

    def test_checksum_size_errors_missing_token_and_no_clobber(self):
        p=self.cfg()
        for before,data,code in [(dict(meta(),sha256Checksum='0'*64),b'leave eligibility','checksum_mismatch'),(meta(),b'x','size_mismatch'),(meta(),b'','body_size_limit')]:
            f=FakeDrive(data,before)
            with self.assertRaises(RagError) as err:pull(p,self.d/'bad',execute=True,transport=f,env_resolver=lambda _:TOKEN)
            self.assertEqual(err.exception.code,code);self.assertEqual(len(f.calls),2);self.assertFalse((self.d/'bad').exists())
        for token in (None,'',TOKEN+'\n'):
            f=FakeDrive()
            with self.assertRaises(RagError):pull(p,self.d/'bad',execute=True,transport=f,env_resolver=lambda _:token)
            self.assertEqual(f.calls,[])
        pull(p,self.d/'good',execute=True,transport=FakeDrive(),env_resolver=lambda _:TOKEN)
        f=FakeDrive()
        with self.assertRaises(RagError):pull(p,self.d/'good',execute=True,transport=f,env_resolver=lambda _:TOKEN)
        self.assertEqual(f.calls,[])
        before=meta();before.pop('sha256Checksum');before.pop('md5Checksum')
        r=pull(p,self.d/'no-checksum',execute=True,transport=FakeDrive(before=before),env_resolver=lambda _:TOKEN)
        self.assertEqual(r['checksum_verification'],{'sha256':'unavailable','md5':'unavailable'})

    def test_output_failures_keep_dispatch_and_no_secrets(self):
        import rag_package.connectors.google_drive as module
        p=self.cfg();original=module.write_json
        for target in ('sources.json','receipt.json'):
            f=FakeDrive()
            def fail(path,value):
                if Path(path).name==target:raise OSError(TOKEN+RESOURCE)
                return original(path,value)
            with patch.object(module,'write_json',side_effect=fail),self.assertRaises(RagError) as err:pull(p,self.d/target,execute=True,transport=f,env_resolver=lambda _:TOKEN)
            self.assertTrue(err.exception.dispatch_attempted);self.assertEqual(err.exception.requests,3);self.no_secrets(str(err.exception));self.assertFalse((self.d/target).exists())
        with patch('rag_package.connectors.google_drive.acquire',side_effect=RuntimeError(TOKEN)),self.assertRaises(RagError) as err:pull(p,self.d/'authfail',execute=True,transport=FakeDrive())
        self.no_secrets(str(err.exception));self.assertFalse(err.exception.dispatch_attempted)

    def test_oauth_files_cached_refresh_and_login(self):
        info=self.info();path=self.private/'credentials.json';self.protected(path,info)
        a={'mode':'oauth_file','credentials_file':str(path)}
        for valid in (True,False):
            backend=FakeAuth(info,valid);token,record=auth.acquire(a,backend=backend)
            self.assertEqual(token,TOKEN);self.assertEqual(record['refresh_requests'],0 if valid else 1)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
        with self.assertRaises(RagError) as err:auth.acquire(a,backend=FakeAuth(info,False,True))
        self.assertEqual(err.exception.code,'auth_error');self.no_secrets(str(err.exception))
        client=self.private/'client.json';self.protected(client,{'installed':{'client_id':'fake','client_secret':'fake','auth_uri':auth.AUTH_URIS[0],'token_uri':auth.TOKEN_URI}})
        out=self.private/'new.json';r=auth.login(client,out,execute=True,backend=FakeAuth(info));self.assertEqual(r['execution_kind'],'test_fixture');self.no_secrets(r)
        with self.assertRaises(RagError):auth.login(client,out,execute=True,backend=FakeAuth(info))
        path.chmod(0o644)
        with self.assertRaises(RagError):auth.acquire(a,backend=FakeAuth(info))
        path.chmod(0o600);sym=self.private/'sym.json';sym.symlink_to(path)
        with self.assertRaises(RagError):auth.acquire({'mode':'oauth_file','credentials_file':str(sym)},backend=FakeAuth(info))
        for change in ({'token_uri':'https://evil.invalid/token'},{'scopes':[]}):
            bad=dict(info,**change);self.protected(path,bad)
            with self.assertRaises(RagError):auth.acquire(a,backend=FakeAuth(info))
        with patch('rag_package.drive_auth.read_secret',side_effect=AssertionError('read')):
            self.assertEqual(auth.login(self.private/'missing',self.private/'new2',execute=False)['status'],'preview')

    def test_real_sdk_import_pkce_signatures_and_restricted_session(self):
        Flow,Credentials,Request,requests=auth.sdk()
        flow=Flow.from_client_config({'installed':{'client_id':'fake','client_secret':'fake','auth_uri':auth.AUTH_URIS[0],'token_uri':auth.TOKEN_URI}},scopes=[SCOPE],autogenerate_code_verifier=True)
        flow.redirect_uri='http://127.0.0.1:12345/'
        url,state=flow.authorization_url();q=parse_qs(urlsplit(url).query)
        self.assertTrue(state);self.assertIn('code_challenge',q);self.assertTrue(flow.code_verifier)
        creds=Credentials.from_authorized_user_info(self.info(),scopes=[SCOPE]);self.assertTrue(creds.valid)
        client={'installed':{'client_id':'fake','client_secret':'fake','auth_uri':auth.AUTH_URIS[0],'token_uri':auth.TOKEN_URI}}
        with patch.object(Flow,'run_local_server',return_value=creds) as run:
            auth.SDKBackend().login(client)
        self.assertEqual(run.call_args.kwargs['host'],'127.0.0.1');self.assertEqual(run.call_args.kwargs['port'],0);self.assertEqual(run.call_args.kwargs['timeout_seconds'],300);self.assertIsNone(run.call_args.kwargs['authorization_prompt_message'])
        session=requests.Session()
        class Response:status_code=200
        with patch.object(session,'send',return_value=Response()) as send:
            count=auth.restrict_session(session);prepared=requests.Request('POST',auth.TOKEN_URI).prepare();session.send(prepared)
            self.assertEqual(count['count'],1);self.assertFalse(session.trust_env);self.assertTrue(send.call_args.kwargs['verify']);self.assertFalse(send.call_args.kwargs['allow_redirects'])
            with self.assertRaises(RagError):session.send(prepared)
            bad=requests.Request('POST','https://evil.invalid/').prepare()
            with self.assertRaises(RagError):session.send(bad)
        session.close()

    def test_installed_sdk_refresh_with_fake_http(self):
        _,Credentials,_,requests=auth.sdk()
        info=self.info();info['expiry']='2000-01-01T00:00:00Z'
        creds=Credentials.from_authorized_user_info(info,scopes=[SCOPE]);self.assertFalse(creds.valid)
        def response(session,request,**kwargs):
            self.assertEqual(request.url,auth.TOKEN_URI);self.assertEqual(request.method,'POST')
            self.assertFalse(kwargs['allow_redirects']);self.assertTrue(kwargs['verify']);self.assertEqual(kwargs['proxies'],{})
            r=requests.Response();r.status_code=200;r._content=json.dumps({'access_token':TOKEN,'expires_in':3600,'token_type':'Bearer','scope':SCOPE}).encode();return r
        with patch.object(requests.Session,'send',autospec=True,side_effect=response) as send,contextlib.redirect_stdout(io.StringIO()) as out:
            count=auth.SDKBackend().refresh(creds)
        self.assertEqual(count,1);self.assertEqual(send.call_count,1);self.assertTrue(creds.valid);self.no_secrets(out.getvalue())

    def test_other_output_boundaries_and_expired_env_token(self):
        p=self.cfg()
        original=Path.write_bytes
        def fail_bytes(path,data):
            if path.name=='download.txt':raise OSError(TOKEN)
            return original(path,data)
        patches=[patch.object(Path,'write_bytes',new=fail_bytes),patch('rag_package.connectors.google_drive.snapshot',side_effect=RagError('fixture_snapshot_failure','snapshot')),patch('rag_package.storage.exclusive_rename',side_effect=RagError('publication_failed','publish'))]
        for n,ctx in enumerate(patches):
            f=FakeDrive()
            with ctx,self.assertRaises(RagError) as err:pull(p,self.d/('output-'+str(n)),execute=True,transport=f,env_resolver=lambda _:TOKEN)
            self.assertTrue(err.exception.dispatch_attempted);self.assertEqual(len(f.calls),3);self.assertFalse((self.d/('output-'+str(n))).exists());self.no_secrets(str(err.exception))
        f=FakeDrive(fail=RagError('auth_error','transport'))
        with self.assertRaises(RagError) as err:pull(p,self.d/'expired',execute=True,transport=f,env_resolver=lambda _:TOKEN)
        self.assertEqual(err.exception.code,'auth_error');self.assertEqual(len(f.calls),1)
        with patch('rag_package.drive_auth.sdk',side_effect=AssertionError('must not import SDK')),patch('rag_package.drive_auth.read_secret',side_effect=AssertionError('secret read')),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(['drive-preview','--config',str(p)]),0)
            self.assertEqual(main(['drive-pull','--config',str(p),'--out',str(self.d/'preview-only')]),0)
        self.no_secrets(out.getvalue());self.assertFalse((self.d/'preview-only').exists())

class DriveHTTPTests(unittest.TestCase):
    def setUp(self):
        self.hits=[];hits=self.hits
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                hits.append(self.path);status=200;body=b'leave eligibility';headers={}
                if self.path.startswith('/error/'):status=int(self.path.split('/')[-1]);body=(TOKEN+RESOURCE).encode()
                elif self.path=='/redirect':status=302;headers['Location']='https://evil.invalid/'+TOKEN
                elif self.path=='/timeout':time.sleep(1.1)
                elif self.path=='/empty':body=b''
                elif self.path=='/partial':headers['Content-Length']='100'
                elif self.path=='/big':body=b'x'*100
                self.send_response(status)
                if 'Content-Length' not in headers:headers['Content-Length']=str(len(body))
                for k,v in headers.items():self.send_header(k,v)
                self.end_headers()
                try:self.wfile.write(body)
                except (BrokenPipeError,ConnectionResetError):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port);port=self.server.server_port
        original=socket.socket.connect;dns=socket.getaddrinfo
        def guarded(sock,address):
            if address[0]!='127.0.0.1' or address[1]!=port:raise AssertionError('non-fixture connection')
            return original(sock,address)
        def guarded_dns(host,p,*a,**kw):
            if host!='127.0.0.1' or int(p)!=port:raise AssertionError('non-fixture DNS')
            return dns(host,p,*a,**kw)
        self.cp=patch.object(socket.socket,'connect',new=guarded);self.dp=patch.object(socket,'getaddrinfo',new=guarded_dns);self.cp.start();self.dp.start()
    def tearDown(self):self.dp.stop();self.cp.stop();self.server.shutdown();self.server.server_close();self.thread.join()
    def test_stream_status_timeout_size_and_no_retry(self):
        self.assertEqual(bounded_get(self.base+'/good',{'Authorization':'Bearer '+TOKEN},100,time.monotonic()+5),b'leave eligibility')
        cases=[('/error/401','auth_error'),('/error/403','access_denied'),('/error/404','not_found_or_inaccessible'),('/error/429','rate_limited'),('/error/503','upstream_error'),('/error/206','partial_response'),('/redirect','redirect_denied'),('/big','body_size_limit'),('/empty','body_size_limit'),('/partial','content_length_mismatch'),('/timeout','timeout')]
        for path,code in cases:
            before=len(self.hits)
            with self.subTest(path=path),self.assertRaises(RagError) as err:bounded_get(self.base+path,{'Authorization':'Bearer '+TOKEN},50 if path=='/big' else 200,time.monotonic()+(.1 if path=='/timeout' else 5))
            self.assertEqual(err.exception.code,code);self.assertEqual(len(self.hits),before+1);self.assertNotIn(TOKEN,str(err.exception));self.assertNotIn(RESOURCE,str(err.exception))
