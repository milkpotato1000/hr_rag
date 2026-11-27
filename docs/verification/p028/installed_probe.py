"""Run only with an installed wheel in a source-free cwd (copied by verifier)."""
import contextlib,hashlib,importlib.metadata,inspect,io,json,os,socket,sys,uuid
from pathlib import Path
from unittest.mock import patch
import rag_package
from rag_package.__main__ import main
from rag_package import workspace
from rag_package.llm.core import invoke
from rag_package.drive_auth import protected_path,SDKBackend,SCOPE,TOKEN_URI
from rag_package.storage import RagError
mode=sys.argv[1];base=Path.cwd();calls=[];sample_name=mode+'-sample-'+uuid.uuid4().hex[:8]
assert 'site-packages' in rag_package.__file__ and str(base) in rag_package.__file__
assert 'PYTHONPATH' not in os.environ
assert not any('/hr_rag_dev' in p for p in sys.path)
def call(args,expected=0):
    stream=io.StringIO()
    with contextlib.redirect_stdout(stream):code=main(args)
    assert code==expected,(args,code,stream.getvalue())
    calls.append({'args':args,'exit_code':code,'stdout':stream.getvalue()})
    return json.loads(stream.getvalue())
original_env_getitem=os._Environ.__getitem__
def guarded_env(self,key):
    if any(x in str(key).upper() for x in ('KEY','TOKEN','SECRET','CREDENTIAL')):raise AssertionError('secret environment read forbidden')
    return original_env_getitem(self,key)
with patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS forbidden')),patch.object(os._Environ,'__getitem__',guarded_env):
    call(['doctor']);call(['init','--out',sample_name]);call(['init','--out',sample_name],2)
    sample=base/(sample_name);call(['doctor','--config',str(sample/'fixed.json')],3)
    call(['snapshot','--sources',str(sample/'sources.json'),'--out',str(sample/'.rag-runs/snapshot')])
    for method in ('fixed','recursive','structure'):
        call(['build','--snapshot',str(sample/'.rag-runs/snapshot'),'--config',str(sample/(method+'.json')),'--out',str(sample/'.rag-runs'/method)])
        call(['ask','--run',str(sample/'.rag-runs'/method),'--config',str(sample/(method+'.json')),'--question','생일 휴가 자격은?','--out',str(sample/'.rag-runs'/('answer-'+method))])
    call(['compare','--snapshot',str(sample/'.rag-runs/snapshot'),'--configs',*[str(sample/(m+'.json')) for m in ('fixed','recursive','structure')],'--questions',str(sample/'questions.json'),'--out',str(sample/'.rag-runs/compare')])
    comp=json.loads((sample/'.rag-runs/compare/comparison.json').read_text());assert len(comp['rows'])==9 and all(not r['dispatch_attempted'] for r in comp['rows'])
    for name in ('llm-local','llm-api'):
        c=json.loads((sample/(name+'.json')).read_text())
        for role in ('generation','evaluation'):
            r=invoke(c,role,[{'role':'user','content':'test'}]);assert r['error']['code']=='configuration_required' and not r['dispatch_attempted']
    call(['drive-preview','--config',str(sample/'drive-token-env.json')])
    call(['drive-pull','--config',str(sample/'drive-token-env.json'),'--out',str(sample/'never')]);assert not (sample/'never').exists()
    import tempfile
    git_test=tempfile.TemporaryDirectory(prefix='p028-git-boundary-',dir='/private/tmp')
    for kind in ('repo','worktree'):
        p=Path(git_test.name).resolve()/kind;p.mkdir();marker=p/'.git'
        if kind=='repo':marker.mkdir()
        else:marker.write_text('gitdir: /SYNTHETIC_NOT_READ')
        private=p/'private';private.mkdir(mode=0o700)
        try:protected_path(private/'credentials.json');raise AssertionError('Git credential accepted')
        except RagError as e:assert e.code=='credential_must_be_outside_repository'
    git_test.cleanup()
    # Outside the active cwd/workspace, in a dedicated directory. Fake path only.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='p028-private-',dir='/private/tmp') as td:
        private=Path(td).resolve();private.chmod(0o700);assert protected_path(private/'fake.json')==private/'fake.json'
    d,code=workspace.doctor();assert code==0
    if mode=='core':
        assert d['optional_dependencies']['pdf']['status']=='missing' and d['optional_dependencies']['drive']['status']=='missing'
        assert 'google_auth_oauthlib' not in sys.modules and 'pypdf' not in sys.modules
    if mode=='extras':
        assert d['optional_dependencies']['pdf']['status']=='available' and d['optional_dependencies']['drive']['status']=='available'
        import pypdf
        from pypdf.generic import NameObject,DecodedStreamObject,DictionaryObject
        pdf=sample/'synthetic.pdf';writer=pypdf.PdfWriter();page=writer.add_blank_page(200,200)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 10 100 Td (Synthetic P028 document) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream)
        writer.write(pdf)
        (sample/'pdf-sources.json').write_text(json.dumps({'schema_version':1,'documents':[{'document_id':'pdf','title':'Synthetic PDF','path':'synthetic.pdf','format':'pdf','synthetic':True}]}))
        call(['snapshot','--sources',str(sample/'pdf-sources.json'),'--out',str(sample/'.rag-runs/pdf')])
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        for fn in (InstalledAppFlow.run_local_server,InstalledAppFlow.from_client_config,Credentials.from_authorized_user_info,Credentials.refresh,Request):assert inspect.signature(fn)
        info={'token':'SYNTHETIC_P028','refresh_token':'SYNTHETIC_REFRESH','token_uri':TOKEN_URI,'client_id':'fake','client_secret':'fake','scopes':[SCOPE],'expiry':'2099-01-01T00:00:00Z'}
        creds=SDKBackend().load(info);assert creds.valid and creds.has_scopes([SCOPE])
report={'mode':mode,'status':'PASS','import_path':rag_package.__file__,'package_version':importlib.metadata.version('milkpotato-rag-lab'),'doctor':d,'comparison_rows':9,'network_requests':0,'secret_reads':0,'calls':calls}
Path(mode+'-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'mode':mode,'status':'PASS','installed_path':rag_package.__file__}))
