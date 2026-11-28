"""Exercise installed guide presets and load saved model artifacts without inference."""
import json,os,sys,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
installed=read(E/'installation.json')
if sys.executable!=installed['python']:os.execv(installed['python'],[installed['python'],'-I',__file__])
from rag_package import reranking,retrieval
root=E.parents[2]
base=Path(installed['base'])
ws=base/'practice';cli=base/'env/bin/rag-lab'
def run(*args,cwd=ws):
    return json.loads(subprocess.check_output([cli,*args],cwd=cwd,text=True))
run('init','--out','practice',cwd=base)
assert (ws/'HANDBOOK.md').read_bytes()==(root/'rag_package/resources/sample/HANDBOOK.md').read_bytes()
s4=Path(read(E.parent/'p032-s4/installation.json')['base'])/'practice'
frozen=read(E/'inputs.json');q=frozen['question']
for model,profile_dir in [('e5','run001'),('bge','continuation001')]:
    profile=root/'.rag-runs/p032-s1-live'/profile_dir/model/'prepared/profile.json'
    path='pair-'+model
    run('pipeline-setup','--llm-config','llm-local.json','--chunk-config','chunk-fixed.json','--method','hybrid',
        '--embedding-config',profile,'--top-k','5','--candidate-k','20','--context-budget-chars','4000','--question',q,'--out',path)
    template=retrieval.config(ws/path/'search.json')[0]
    artifact=s4/('.rag-runs/e5' if model=='e5' else 's24-pair/index')
    _,_,chunks=retrieval.load_build(artifact,template)
    assert len(chunks)==121
    for stage in ['build','ask','candidates','rerank']:
        subprocess.run([cli,stage,'--help'],cwd=ws,stdout=subprocess.DEVNULL,check=True)
for artifact in ['.rag-runs/off','.rag-runs/on','s24-pair/reranked']:
    result,parent,_,_=reranking.load(s4/artifact)
    assert result['status']=='complete' and parent['candidate_fingerprint']==frozen['candidates']
print('Installed handbook, two Hybrid profiles, two saved indexes, three reranker outputs verified; new inference 0.')
