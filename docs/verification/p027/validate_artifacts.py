"""P027 bounded offline checks; no auth/model/Drive execution."""
from pathlib import Path
import ast,hashlib,json,re,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
commands=[]
def run(args):
    r=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
    assert r.returncode==0,(args,r.stdout,r.stderr)
    commands.append({'args':args,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
    return r.stdout
with tempfile.TemporaryDirectory(dir=ROOT/'.rag-runs',prefix='p027-check-') as temp:
    out=Path(temp)/'unused'
    for name in ('token-env','oauth-file'):
        for op in ('drive-preview','drive-pull'):
            args=[sys.executable,'-m','rag_package',op,'--config',f'examples/drive/{name}.json']
            if op=='drive-pull':args+=['--out',str(out)]
            value=json.loads(run(args));assert value['status']=='preview' and value['requests']==0 and not value['remote_access_verified']
            assert not out.exists()
    value=json.loads(run([sys.executable,'-m','rag_package','drive-login','--client-secret-file','/SYNTHETIC_PRIVATE/client.json','--credentials-file','/SYNTHETIC_PRIVATE/credentials.json']))
    assert value['auth_requests']==0
    run(['git','check-ignore',str(out)])
links=[]
for p in [ROOT/'README.md',*sorted((ROOT/'docs/learning/rag-package').glob('*.md')),OUT/'README.md']:
    s=p.read_text();assert s.count('```')%2==0,p
    for m in re.finditer(r'!?\[[^\]]*\]\((<[^>]+>|[^)]+)\)',s):
        target=m.group(1).strip('<>')
        if target.startswith(('https://','http://')):continue
        assert (p.parent/target.split('#')[0]).exists() or (p.parent/target).resolve()==OUT/'checks.json',(p,target)
        links.append({'file':str(p.relative_to(ROOT)),'target':target})
for p in (ROOT/'rag_package').rglob('*.py'):ast.parse(p.read_text(),feature_version=(3,10))
before=json.loads((OUT/'preservation-before.json').read_text())
changed=[p for p,h in before.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
assert set(changed)=={'rag_package/documents.py','rag_package/rag.py','rag_package/__main__.py'},changed
assert '> 실행: 차단' in (ROOT/'docs/planning/plans/P013.md').read_text()
lock=(ROOT/'rag_package/requirements-drive.lock').read_text()
assert 'google-auth==2.63.1' in lock and 'google-auth-oauthlib==1.5.0' in lock
assert (ROOT/'rag_package/requirements-pdf.lock').read_bytes()==(ROOT/'2. Document Chunking/ingestion-requirements.lock').read_bytes()
for p in [*(ROOT/'rag_package').rglob('*.py'),*(ROOT/'examples/drive').glob('*.json')]:
    assert not re.search(r'(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN .*PRIVATE KEY-----)',p.read_text())
run([sys.executable,'scripts/contract_guard.py','check']);run(['git','diff','--check'])
report={'status':'PASS','python':sys.version,'commands':commands,'links_checked':len(links),'links':links,'baseline_files':len(before),'preserved_files':len(before)-len(changed),'allowed_origin_cli_extensions':changed,'p013_blocked':True,'actual_drive_oauth_user_key_model_api_calls':0,'recovery_grant_consumed':False,'model_downloads_server_starts':0,'sdk_pypi_installation':True,'live_e2e':'not_verified','visual_render_observed':False}
(OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('status','links_checked','preserved_files','allowed_origin_cli_extensions')},ensure_ascii=False))
