"""Source-free installation, immutable S4 parent, no-inference previews."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import *
from rag_package.llm.core import hash_json
from rag_package.storage import verify

inst=read(E/'installation.json')
base=Path(inst['base'])
assert sys.executable==inst['python']
ws=base/'practice'
cli=base/'env/bin/rag-lab'
def run(*args):
    return json.loads(subprocess.check_output([cli,*args],cwd=ws if ws.exists() else base,text=True))
run('init','--out','practice')
s4=E.parent/'p032-s4'
src=Path(read(s4/'installation.json')['base'])/'practice/.rag-runs/on'
ranks=read(s4/'ranks.json')
result=read(src/'result.json')
verify(src,'rerank')
assert result['candidate_fingerprint']==ranks['candidate_fingerprint']
assert [r['id'] for r in ranks['results']['on']]==[r['chunk_id'] for r in result['selection']['ranking']]
parent={str(p):sha(p) for p in src.rglob('*') if p.is_file()}
for folder in [s4,E.parent/'p032-s3']:
    parent.update({str(p):sha(p) for p in folder.iterdir() if p.is_file()})
write(E/'parent-hashes.json',parent)
shutil.copytree(src,ws/'.rag-runs/on')
for dst in [E/'profile.json',ws/'handbook-model.json']:
    shutil.copyfile(E.parent/'p032-s3/profile.json',dst)
run('llm-configure','--spec','llm-spec-api.json','--out','handbook-api.json')
for label,profile in [('local','handbook-model.json'),('api','handbook-api.json')]:
    run('answer-from-rerank','--run','.rag-runs/on','--llm-config',profile,'--out','.rag-runs/'+label)
comp=run('compare-answers','--result','local','.rag-runs/local','--result','api','.rag-runs/api')
assert comp['same_input'] and all(r['generation_requests']==0 and r['answer'] is None for r in comp['rows'])
write(E/'two-previews.json',comp)
p=read(ws/'.rag-runs/local/result.json')
site=next((base/'env/lib').glob('python*/site-packages'))
inputs={str(x):sha(x) for x in (ws/'.rag-runs/on').rglob('*') if x.is_file()}
write(E/'frozen.json',dict(python=sys.executable,practice=str(ws),wheel=inst['wheel'],wheel_sha256=inst['wheel_sha256'],installed_files={str(site/n):h for n,h in inst['wheel_payload_hashes'].items()},input_files=inputs,profile_sha256=sha(E/'profile.json'),scripts={f.name:sha(f) for f in E.glob('*.py')},rows=[dict(question_id='first',question=p['question'],actual_messages_hash=p['actual_messages_hash'],body_hash=hash_json(p['preview']['body']))]))
verify_parent()
