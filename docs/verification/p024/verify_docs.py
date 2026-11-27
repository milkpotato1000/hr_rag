"""P024 bounded offline document verification; never dispatches models."""
from pathlib import Path
import hashlib,json,re,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
GUIDE=ROOT/'docs/learning/rag-package'
def run(args):
    p=subprocess.run(args,cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,(args,p.stderr,p.stdout)
    return {'args':args,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def shape(v):
    if isinstance(v,dict):return {k:shape(x) for k,x in v.items()}
    return None
local=json.loads((GUIDE/'examples/local.json').read_text())
api=json.loads((GUIDE/'examples/api.json').read_text())
assert shape(local)==shape(api)
assert all(x['example_only'] is True for x in (local,api))
assert set(local)=={'example_only','schema_status','source','llm','chunking','embedding','retrieval','reranker','evaluation'}
assert {k:v for k,v in local.items() if k!='llm'}=={k:v for k,v in api.items() if k!='llm'}
assert api['llm']['generation']['api_key_env']=='RAG_LLM_API_KEY'
assert (ROOT/local['source']['path']).is_file()
links=[];pages=[ROOT/'README.md',*sorted(GUIDE.glob('*.md'))]
for page in pages:
    text=page.read_text()
    assert text.count('```')%2==0,page
    assert not re.search(r'(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN .*PRIVATE KEY-----)',text)
    for m in re.finditer(r'!?\[[^\]]*\]\((<[^>]+>|[^)]+)\)',text):
        href=m.group(1).strip('<>')
        if re.match(r'https?://',href):continue
        path=href.split('#')[0]
        assert (page.parent/path).exists(),(page,href)
        links.append({'page':str(page.relative_to(ROOT)),'target':href})
for p in (GUIDE/'examples').glob('*.json'):
    text=p.read_text()
    assert not re.search(r'"(?:api_key|token|secret|password)"\s*:',text)
before=json.loads((OUT/'preservation-before.json').read_text())
changed=[p for p,h in before['files'].items() if digest(ROOT/p)!=h]
assert not changed,changed
old=subprocess.check_output(['git','show','87d664f:docs/planning/plans/P013.md'],cwd=ROOT,text=True)
now=(ROOT/'docs/planning/plans/P013.md').read_text()
assert '> 실행: 차단' in now
assert old.split('<!-- EXECUTION:START -->')[1]==now.split('<!-- EXECUTION:START -->')[1]
assert '- [x] C1:' in now
commands=[run(['python3','-m','json.tool',str(p.relative_to(ROOT))]) for p in sorted((GUIDE/'examples').glob('*.json'))]
commands.append(run(['python3','scripts/contract_guard.py','check']))
commands.append(run(['python3','scripts/work_queue.py','--owner','dev']))
commands.append(run(['python3','1. Naive RAG/scripts/run_bm25_baseline.py','--help']))
with tempfile.TemporaryDirectory(prefix='p024-bm25-') as td:
    result=run(['python3','1. Naive RAG/scripts/run_bm25_baseline.py','--chunks','1. Naive RAG/data/synthetic/chunks.jsonl','--queries','1. Naive RAG/data/synthetic/queries.jsonl','--top-k','20','--k','5','10','20','--output-dir',str(Path(td)/'result')])
    commands.append(result)
    bm25={p.name:json.loads(p.read_text()) for p in (Path(td)/'result').glob('*.json')}
report={'status':'PASS','local_links_checked':len(links),'links':links,'json_examples':2,'identical_structure':True,'non_llm_values_identical':True,'preserved_files':len(before['files']),'preservation_mismatches':changed,'p013_blocked_and_history_preserved':True,'secret_pattern_scan':'PASS (bounded patterns; not a universal secret detector)','flow_diagram':'plain text; fenced block/source structure inspected; no Mermaid dependency','external_sources':'four official HF model cards opened 2026-11-27; see models-and-support.md','commands':commands,'offline_bm25_json':bm25,'not_performed':['model inference','model download','server start','paid API call','browser/render verification','live local/API parity','installation in clean environment']}
(OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('status','local_links_checked','json_examples','preserved_files','p013_blocked_and_history_preserved')},ensure_ascii=False))
