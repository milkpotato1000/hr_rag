"""Independent checks on actual browser jobs and the imported S8 output."""
from pathlib import Path
import hashlib,json
E=Path(__file__).resolve().parent
def read(p):
    return json.loads(p.read_text())
ws=Path(read(E/'installation.json')['base'])/'practice'
root=ws/'.rag-runs/ui'
jobs=[read(p) for p in (root/'jobs').glob('*.json')]
registry=read(root/'registry.json')['artifacts']
cli=read(E/'cli-preview.json')
views=[]
for job in jobs:
    if job['kind']!='pipeline': continue
    result=read(ws/registry[job['artifact_ids'][0]]['path']/'pipeline.json')
    if result['plan']['retrieval']['method']=='hybrid':
        assert result['plan']==cli['plan'] and result['question']==cli['question']
        assert result['status']=='preview'
    views.append({'status':result['status'],'kind':result['execution_kind'],'retrieval':result['plan']['retrieval']['method'],'job':job['status'],'requests':result.get('generation_requests'),'error':result.get('error')})
assert sorted(r['status'] for r in views)==['answered','failed','preview','preview','preview']
assert (E/'fixture-calls.log').read_text().splitlines()==['success','failure']
original=Path(read(E.parent/'p032-s8/frozen.json')['practice'])/'.rag-runs/pipeline-live'
dest=ws/'.rag-runs/pipeline-live'
assert {p.relative_to(dest) for p in dest.rglob('*') if p.is_file()}=={p.relative_to(original) for p in original.rglob('*') if p.is_file()}
assert all((dest/p.relative_to(original)).read_bytes()==p.read_bytes() for p in original.rglob('*') if p.is_file())
assert read(dest/'pipeline.json')['answer']['answer']=='3영업일 전'
(E/'verified.json').write_text(json.dumps({'actual_model_calls':0,'fixture_posts':2,'cli_ui_hybrid_plan_equal':True,'s8_copy_byte_identical':True,'browser_jobs':views},ensure_ascii=False,indent=2)+'\n')
