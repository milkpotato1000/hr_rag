import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p012';stage=root/'1. Naive RAG';candidate=stage/'variants/langchain'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=read(ev/'before.json');allow={'1. Naive RAG/'+x for x in ['README.md','LEARNING_GUIDE.md','stage-manifest.json']}
allow|={'1. Naive RAG/variants/langchain/'+x for x in ['scripts/comparison.py','scripts/ask_compare.py','scripts/serve_compare.py','tests_langchain/test_comparison_http.py','web_compare/index.html','web_compare/app.js','web_compare/style.css','README.md','LEARNING_GUIDE.md','stage-manifest.json','copy-manifest.json']}
changed=[]
for path,old in before['files'].items():
 new=sha(root/path)
 if new!=old:
  assert path in allow,path
  changed.append({'path':path,'before_sha256':old,'current_sha256':new})
manifest_path=candidate/'copy-manifest.json';manifest=read(manifest_path)
for row in manifest['files']:
 row['current_sha256']=sha(candidate/row['path']);row['original_current_sha256']=sha(stage/row['path'])
for row in manifest['candidate_only_files']:
 row.setdefault('initial_sha256',row['sha256']);row['sha256']=sha(candidate/row['path'])
for name in ['web_compare/implementation.html','tests_learning/test_learning_routes.py']:
 if not any(r['path']==name for r in manifest['candidate_only_files']):manifest['candidate_only_files'].append({'path':name,'sha256':sha(candidate/name),'introduced_by':'P012'})
manifest['p012_revision']={'baseline_commit':before['baseline'],'adopted_plan':before['adopted_plan'],'reason':'LangChain learning default and separate implementation experiment; pipeline and P011 evidence unchanged','changes':[x for x in changed if not x['path'].endswith('copy-manifest.json')],'original_manifest_sha256':before['files']['1. Naive RAG/variants/langchain/copy-manifest.json']}
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
assert sha(candidate/'adoption-decision.json')==before['files']['1. Naive RAG/variants/langchain/adoption-decision.json']
for p in (root/'docs/verification/p011').rglob('*'):
 if p.is_file() and '__pycache__' not in p.parts:assert str(p.relative_to(root)) in before['files'],p
(ev/'preservation.json').write_text(json.dumps({'status':'PASS','baseline':before['baseline'],'protected_files_checked':len(before['files']),'allowed_changes':changed,'original_direct_and_candidate_pipeline_unchanged':True,'p011_evidence_and_decision_unchanged':True,'current_manifest_sha256':sha(manifest_path)},ensure_ascii=False,indent=2)+'\n')
print('preservation PASS',len(before['files']))
