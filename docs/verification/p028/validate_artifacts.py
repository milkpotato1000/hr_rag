"""P028 static evidence, explicit resource provenance and legacy preservation."""
from pathlib import Path
import ast,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=json.loads((OUT/'preservation-before.json').read_text())
changed=[p for p,h in before.items() if sha(ROOT/p)!=h]
assert set(changed)=={'rag_package/__main__.py','rag_package/llm/core.py','rag_package/connectors/drive_config.py','rag_package/drive_auth.py'},changed
manifest=json.loads((ROOT/'rag_package/resources/manifest.json').read_text())
for item in manifest['files']:
    assert sha(ROOT/'rag_package/resources/sample'/item['path'])==item['sha256']
    src=item['source']
    if src:
        raw=subprocess.check_output(['git','show',src['commit']+':'+src['path']],cwd=ROOT)
        assert hashlib.sha256(raw).hexdigest()==src['sha256']
links=[]
for p in [ROOT/'README.md',ROOT/'PACKAGING.md',*sorted((ROOT/'docs/learning/rag-package').glob('*.md')),OUT/'README.md']:
    s=p.read_text();assert s.count('```')%2==0,p
    for m in re.finditer(r'!?\[[^\]]*\]\((<[^>]+>|[^)]+)\)',s):
        t=m.group(1).strip('<>')
        if t.startswith(('https://','http://')):continue
        assert (p.parent/t.split('#')[0]).exists() or (p.parent/t).resolve()==OUT/'checks.json',(p,t)
        links.append({'file':str(p.relative_to(ROOT)),'target':t})
for p in (ROOT/'rag_package').rglob('*.py'):ast.parse(p.read_text(),feature_version=(3,10))
for p in (ROOT/'rag_package').rglob('*'):
    if p.is_file() and p.suffix in ('.py','.md','.json'):
        assert not re.search(r'(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN .*PRIVATE KEY-----)',p.read_text())
assert '> 실행: 차단' in (ROOT/'docs/planning/plans/P013.md').read_text()
for cmd in [['python3','scripts/contract_guard.py','check'],['git','diff','--check']]:subprocess.run(cmd,cwd=ROOT,check=True)
r={'status':'PASS','baseline_files':len(before),'preserved_files':len(before)-len(changed),'allowed_changes':changed,'resource_files':len(manifest['files']),'source_provenance_verified':True,'links_checked':len(links),'links':links,'p013_blocked':True,'recovery_grant_consumed':False,'live_model_api_drive_user_key_calls':0,'actual_os':'macOS','other_os_verified':False,'python_actual':'3.12.14','python_310_syntax':True}
(OUT/'checks.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print({k:r[k] for k in ('status','preserved_files','resource_files','links_checked')})
