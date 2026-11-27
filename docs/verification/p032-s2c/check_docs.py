"""Bounded Markdown link graph, current entry reachability, resource and help checks."""
from pathlib import Path
import hashlib,json,re,subprocess
from urllib.parse import unquote,urlsplit
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
files=sorted((ROOT/'docs/learning/rag-package').glob('*.md'))+[OUT/'README.md']
links=[];bad=[]
for p in files:
    body=re.sub(r'```.*?```','',p.read_text(),flags=re.S)
    for m in re.finditer(r'\[[^\]]*\]\((<[^>]+>|[^\s)]+)\)',body):
        target=m[1].strip('<>');url=urlsplit(target)
        if url.scheme or not url.path:continue
        dest=(p.parent/unquote(url.path)).resolve()
        links.append({'from':str(p.relative_to(ROOT)),'to':str(dest.relative_to(ROOT))})
        if not dest.exists():bad.append(links[-1])
assert not bad,bad
entry='docs/learning/rag-package/README.md';adj={}
for e in links:adj.setdefault(e['from'],set()).add(e['to'])
seen=set();todo=[entry]
while todo:
    n=todo.pop()
    if n not in seen:seen.add(n);todo.extend(adj.get(n,()))
required=['install-current.md','model-preparation.md','document-rag.md','model-chunking.md','hybrid.md','reranking.md','live-retrieval-s1.md','chunk-comparison-live.md','providers.md','ui.md']
assert all('docs/learning/rag-package/'+n in seen for n in required)
manifest=json.loads((ROOT/'rag_package/resources/manifest.json').read_text())
for item in manifest['files']:assert hashlib.sha256((ROOT/'rag_package/resources/sample'/item['path']).read_bytes()).hexdigest()==item['sha256']
commands=json.loads((OUT/'commands.json').read_text())
help_commands=[c['args'][-2] for c in commands if c['args'][-1]=='--help'];assert set(help_commands)=={'init','doctor','snapshot','build','ask','compare','chunk','chunk-replay','chunk-report','llm-configure','model-plan','model-prepare','serve','rerank'}
for c in commands:assert c['exit_code']==c['expected']
# Record the previous entry graph to make the changed navigation reviewable.
before=subprocess.check_output(['git','show','af524c65f31504e85e390677784417f5a7cb6186:'+entry],cwd=ROOT,text=True)
before_links=re.findall(r'\[[^\]]*\]\((<[^>]+>|[^\s)]+)\)',before)
result={'status':'PASS','pages':len(files),'relative_links':len(links),'broken_links':bad,'entry_reaches':required,'links':links,'previous_entry_targets':before_links,'resource_files':len(manifest['files']),'help_commands':help_commands,'markdown_anchors':'No new fragment links; existing fragments not revalidated','mermaid':'No Mermaid added or changed','serve_and_execute_options':'Checked in installed help only; no server or model execution'}
(OUT/'docs-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('PASS',len(files),'pages',len(links),'local links')
