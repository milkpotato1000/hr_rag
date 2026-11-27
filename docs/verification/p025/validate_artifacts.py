"""Offline P025 artifact checks. Does not invoke providers."""
from pathlib import Path
import ast,hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from rag_package.llm import read_json, validate_config, validate_messages

def run(args):
    p=subprocess.run(args,cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,(args,p.stdout,p.stderr)
    return {'args':args,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}

commands=[run([sys.executable,'-m','rag_package.llm','--help'])]
for name in ('local','openai','anthropic'):
    path='examples/llm/'+name+'.json'
    validate_config(read_json(ROOT/path))
    commands.append(run([sys.executable,'-m','rag_package.llm','validate','--config',path]))
    commands.append(run([sys.executable,'-m','rag_package.llm','preview','--config',path,'--role','generation','--messages','examples/llm/messages.json']))
validate_messages(read_json(ROOT/'examples/llm/messages.json'))
# Digests are quoted from the existing locks, not discovered or changed by P025.
local=read_json(ROOT/'examples/llm/local.json')
lock4=read_json(ROOT/'1. Naive RAG/variants/langchain/generation-lock.json')
lock8=read_json(ROOT/'docs/verification/p019/model-lock.json')
assert local['profiles']['answer']['identity']['expected_digest']==lock4['model']['digest']
assert local['profiles']['judge']['identity']['expected_digest']==lock8['digest']
links=[]
for path in [ROOT/'README.md',*sorted((ROOT/'docs/learning/rag-package').glob('*.md')),OUT/'README.md']:
    text=path.read_text()
    assert text.count('```')%2==0,path
    for m in re.finditer(r'!?\[[^\]]*\]\((<[^>]+>|[^)]+)\)',text):
        target=m.group(1).strip('<>')
        if target.startswith(('https://','http://')):continue
        assert (path.parent/target.split('#')[0]).exists(),(path,target)
        links.append({'file':str(path.relative_to(ROOT)),'target':target})
for path in (ROOT/'rag_package').rglob('*.py'):
    ast.parse(path.read_text(),feature_version=(3,10))
for path in (ROOT/'examples/llm').glob('*.json'):
    text=path.read_text()
    assert not re.search(r'"(?:api_key|token|password|secret)"\s*:',text)
for path in [*(ROOT/'rag_package').rglob('*.py'),*(ROOT/'examples/llm').glob('*.json'),*(ROOT/'docs/learning/rag-package').glob('*.md')]:
    assert not re.search(r'(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN .*PRIVATE KEY-----)',path.read_text())
before=json.loads((OUT/'preservation-before.json').read_text())
changed=[p for p,h in before.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
assert not changed,changed
assert '> 실행: 차단' in (ROOT/'docs/planning/plans/P013.md').read_text()
commands.append(run([sys.executable,'scripts/contract_guard.py','check']))
commands.append(run(['git','diff','--check']))
report={'status':'PASS','python':sys.version,'local_links':links,'link_count':len(links),'examples_validated':3,'messages_validated':1,'source_digest_examples_match_locks':True,'preserved_files':len(before),'mismatches':changed,'p013_blocked_unchanged':True,'syntax_target':'3.10','secret_check':'bounded key/private-key patterns and no credential-value JSON field','commands':commands,'actual_provider_calls':0,'actual_user_key_reads':0,'model_server_starts':0,'model_downloads':0,'paid_api_calls':0,'render_observed':False}
(OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('status','link_count','examples_validated','preserved_files','p013_blocked_unchanged')},ensure_ascii=False))
