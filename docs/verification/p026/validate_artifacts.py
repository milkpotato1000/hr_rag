"""P026 bounded offline CLI and preservation verification."""
from pathlib import Path
import ast,hashlib,json,re,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from rag_package.storage import read_json,verify
from rag_package.documents import load_snapshot
from rag_package.retrieval import config,load_build

def run(args):
    p=subprocess.run(args,cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,(args,p.stdout,p.stderr)
    return {'args':args,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}

commands=[run([sys.executable,'-m','rag_package','--help'])]
for name in ('fixed','recursive','structure'):config(ROOT/'examples/rag'/f'{name}.json')
private=ROOT/'.rag-runs';private.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='p026-verification-',dir=private) as td:
    base=Path(td).relative_to(ROOT);snap=str(base/'snapshot');built=str(base/'fixed');answer=str(base/'answer');comp=str(base/'comparison')
    for args in [
        ['snapshot','--sources','examples/rag/sources.json','--out',snap],
        ['build','--snapshot',snap,'--config','examples/rag/fixed.json','--out',built],
        ['ask','--run',built,'--config','examples/rag/fixed.json','--question','생일 휴가 자격과 사용 기간은?','--out',answer],
        ['compare','--snapshot',snap,'--configs','examples/rag/fixed.json','examples/rag/recursive.json','examples/rag/structure.json','--questions','examples/rag/questions.json','--out',comp]]:
        commands.append(run([sys.executable,'-m','rag_package',*args]))
    sm,docs=load_snapshot(ROOT/snap);bm,_,chunks=load_build(ROOT/built,config(ROOT/'examples/rag/fixed.json')[0])
    ar=read_json(ROOT/answer/'result.json');cr=read_json(ROOT/comp/'comparison.json')
    assert ar['status']=='preview' and not ar['dispatch_attempted'] and ar['provider_result'] is None
    assert len(cr['rows'])==9 and all(not r['dispatch_attempted'] for r in cr['rows'])
    assert cr['execution_kind']=='preview' and cr['cost'] is None
    assert all(r['metrics']['faithfulness']['value'] is None for r in cr['rows'])
    commands.append(run(['git','check-ignore',str(base/'answer/result.json')]))
    cli_summary={'source_fingerprint':sm['fingerprint'],'documents':len(docs),'chunks':len(chunks),'chunk_fingerprint':bm['identity']['chunk_fingerprint'],'index_fingerprint':bm['identity']['index_fingerprint'],'answer_status':ar['status'],'comparison_rows':len(cr['rows']),'comparison_status_counts':cr['status_counts'],'changed_axes':[r['changed_axes_vs_first'] for r in cr['configs']],'dispatches':0}
links=[]
for p in [ROOT/'README.md',*sorted((ROOT/'docs/learning/rag-package').glob('*.md')),OUT/'README.md']:
    text=p.read_text();assert text.count('```')%2==0,p
    for match in re.finditer(r'!?\[[^\]]*\]\((<[^>]+>|[^)]+)\)',text):
        target=match.group(1).strip('<>')
        if target.startswith(('https://','http://')):continue
        assert (p.parent/target.split('#')[0]).exists(),(p,target)
        links.append({'file':str(p.relative_to(ROOT)),'target':target})
for p in (ROOT/'rag_package').rglob('*.py'):ast.parse(p.read_text(),feature_version=(3,10))
for p in (ROOT/'examples/rag').glob('*.json'):read_json(p)
for p in [*(ROOT/'rag_package').rglob('*.py'),*(ROOT/'examples/rag').rglob('*')]:
    if p.is_file() and p.suffix in ('.py','.json','.md','.txt'):
        assert not re.search(r'(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN .*PRIVATE KEY-----)',p.read_text())
before=read_json(OUT/'preservation-before.json')
changed=[p for p,h in before.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h];assert not changed,changed
provenance=read_json(ROOT/'rag_package/provenance.json')
for r in provenance['sources']:
    data=subprocess.check_output(['git','show',r['commit']+':'+r['path']],cwd=ROOT)
    assert hashlib.sha256(data).hexdigest()==r['sha256']
assert (ROOT/'rag_package/requirements-pdf.lock').read_bytes()==(ROOT/'2. Document Chunking/ingestion-requirements.lock').read_bytes()
commands.append(run([sys.executable,'scripts/contract_guard.py','check']));commands.append(run(['git','diff','--check']))
report={'status':'PASS','python':sys.version,'cli':cli_summary,'links_checked':len(links),'links':links,'preserved_files':len(before),'preservation_mismatches':changed,'p013_blocked_unchanged':'> 실행: 차단' in (ROOT/'docs/planning/plans/P013.md').read_text(),'provenance_verified':True,'pdf_lock_reused':True,'commands':commands,'model_api_user_key_calls':0,'model_server_starts':0,'downloads':0,'visual_render_observed':False}
(OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('status','cli','links_checked','preserved_files','p013_blocked_unchanged')},ensure_ascii=False))
