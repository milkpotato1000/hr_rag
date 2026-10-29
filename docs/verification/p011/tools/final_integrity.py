"""Read-only final source and quiescent index checks; writes evidence only."""
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p011'
original=root/'1. Naive RAG';candidate=original/'variants/langchain'
sys.path.insert(0,str(candidate/'scripts'))
from copy_indexes import logical
manifest=json.loads((candidate/'copy-manifest.json').read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
allowed={'README.md','LEARNING_GUIDE.md','stage-manifest.json'}
for item in manifest['files']:
 name=item['path'];assert sha(original/name)==item['original_current_sha256'],name
 assert sha(candidate/name)==item['current_sha256'],name
 if name not in allowed:assert sha(original/name)==item['source_sha256']==sha(candidate/name),name
baseline=manifest['source_commit']
for item in manifest['candidate_only_files']:
 assert sha(candidate/item['path'])==item['sha256'],item['path']
historical=subprocess.check_output(['git','diff','--name-only',baseline,'--',*[f'docs/verification/p{i:03}' for i in range(1,10)]],cwd=root,text=True).splitlines()
assert not historical,historical
report=json.loads((ev/'preservation-check.json').read_text());report['final_manifest_recheck']=True
(ev/'preservation-check.json').write_text(json.dumps(report,indent=2)+'\n')
copies=json.loads((ev/'copy-location.json').read_text());records=[]
for item in json.loads((ev/'index-preservation.json').read_text()):
 name=item['index'];expected=item['export_sha256'];hashes={}
 for label,stage in [('original',original),('candidate',candidate),('standalone',Path(copies['path']))]:
  hashes[label]=logical(stage/'.runtime'/name);assert hashes[label]==expected,(label,name)
  assert (stage/'.runtime'/name/'index-manifest.json').read_bytes()==(original/'.runtime'/name/'index-manifest.json').read_bytes()
 records.append({'index':name,'point_count':item['point_count'],'logical_hashes':hashes,'manifest_bytes_equal':True})
(ev/'index-final-check.json').write_text(json.dumps({'status':'PASS','checks':records},indent=2)+'\n')
print('preserved93 source files and both original/candidate/standalone indexes: PASS')
