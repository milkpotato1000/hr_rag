"""Reuse S4 installed artifacts and run only the missing BGE workers."""
from pathlib import Path
import contextlib,hashlib,io,json,os,runpy,shutil,sys

E=Path(__file__).resolve().parent
S4=E.parent/'p032-s4'
ROOT=E.parents[2]
def read(p):return json.loads(p.read_text())
def save(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
install=read(S4/'installation.json')
ws=Path(install['base'])/'practice'
old=ws/'.rag-runs'
new=ws/'s24-pair'
profiles=ROOT/'.rag-runs/p032-s1-live'
models={name:profiles/parent/name/'prepared/profile.json' for name,parent in [
    ('e5','run001'),('mmini','run001'),('bge','continuation001'),('bge-reranker','continuation001')]}
question=read(S4/'freeze.json')['question']
config=new/'hybrid.json'
def audit():
    from rag_package import embedding,reranker,reranking,candidates
    frozen=read(S4/'freeze.json')
    assert all(sha(Path(p))==v for p,v in frozen['inputs'].items())
    for name,h in install['wheel_payload_hashes'].items():
        assert sha(Path(install['base'])/'env/lib/python3.12/site-packages'/name)==h
    identities={}
    for name,path in models.items():
        mod=reranker if name in ('mmini','bge-reranker') else embedding
        p=mod.read_profile(path);mod.check_files(p);mod.versions()
        assert p['device']=='cpu' and p['batch_size']==1 and p['timeout_seconds']<=300
        identities[name]=mod.identity(p)
    idx=read(old/'e5/index.json')
    assert idx['identity']['embedding']==identities['e5'] and idx['identity']['execution_kind']=='local_hf'
    cand,_,corpus=candidates.load(old/'candidates')
    original=read(old/'hybrid/result.json')
    assert original==read(old/'candidates/parent-result.json') and original['question']==question
    assert original['embedding_work']['jobs']==1 and read(S4/'ledger.json')['status']=='complete'
    assert cand['actual_n']==20 and corpus==read(old/'e5/chunks.json')
    for mode in ('on','off'):
        r,parent,_,_=reranking.load(old/mode)
        assert parent==cand and r['status']=='complete' and r['candidate_fingerprint']==cand['candidate_fingerprint']
        if mode=='on':assert r['profile_identity']==identities['mmini']
    return dict(question=question,models=identities,source=cand['source_fingerprint'],chunks=cand['chunk_fingerprint'],
                candidates=cand['candidate_fingerprint'],e5_index=idx['fingerprint'],
                parents={name:sha(old/name/'manifest.json') for name in ('pdf','e5','hybrid','candidates','off','on')})

def invoke(*args):
    from rag_package.__main__ import main
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):
        code=main(list(map(str,args)))
    if code:raise RuntimeError(buf.getvalue()[-800:])

def prepare():
    frozen=audit()
    new.mkdir()
    c=read(ws/'handbook-hybrid.json')
    c.update(embedding_config=str(models['bge']),llm_config=str(ws/'llm-local.json'))
    save(config,c)
    save(E/'inputs.json',dict(**frozen,config_sha256=sha(config),config=c,order=['bge-index','bge-query','bge-rerank']))

def live():
    from rag_package.owned_worker import execution_scope
    from rag_package.model_process import pressure
    inputs=read(E/'inputs.json')
    assert all(inputs[k]==v for k,v in audit().items()) and sha(config)==inputs['config_sha256']
    control=runpy.run_path(str(E.parent/'p032-s1/live_control.py'))['Control']
    control.before_spawn.__globals__['LIMITS']={'embedding_full':2,'reranker_full':1}
    ledger=E/'ledger.json'
    with ledger.open('x') as f:
        json.dump(dict(status='ready',active=None,jobs=[],started_at=None,reservations={'embedding_full':0,'reranker_full':0},reranker_full_pairs=0),f)
    c=control(ledger)
    def job(label,args,pairs=0):
        assert label==inputs['order'][len(c.state['jobs'])]
        with c.job(label,'reranker_full' if pairs else 'embedding_full',pairs) as row:
            pressure()
            assert shutil.disk_usage(new).free>=2*1024**3
            invoke(*args)
            assert row['workers_started']==1 and row['observation']['resume_safe']
    with execution_scope(c):
        job('bge-index',['build','--snapshot',old/'pdf','--config',config,'--out',new/'index','--execute-retrieval'])
        assert read(old/'e5/chunks.json')==read(new/'index/chunks.json')
        job('bge-query',['ask','--run',new/'index','--config',config,'--question',question,'--out',new/'hybrid','--execute-retrieval'])
        assert read(old/'hybrid/result.json')['retrieval_trace']['bm25']==read(new/'hybrid/result.json')['retrieval_trace']['bm25']
        job('bge-rerank',['rerank','--candidates',old/'candidates','--method','cross-encoder','--profile',models['bge-reranker'],
            '--top-k','5','--context-budget-chars','4000','--out',new/'reranked','--execute-reranking'],20)
    c.state['status']='complete';c.save()

if __name__=='__main__':
    if sys.executable!=install['python']:
        os.execv(install['python'],[install['python'],'-I',__file__,*sys.argv[1:]])
    os.chdir(ws)
    (prepare if sys.argv[1]=='prepare' else live)()
