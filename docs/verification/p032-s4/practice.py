"""Reproduce installed handbook commands. Split model-free freeze and one-shot live."""
import contextlib
import hashlib
import importlib.metadata as md
import io
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import sys

E = Path(__file__).resolve().parent
ROOT = E.parents[2]
def read(path):
    return json.loads(Path(path).read_text())
def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

install = read(E/'installation.json')
base = Path(install['base'])
ws = base/'practice'
Q = '생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'
source = ROOT/'.rag-runs/p032-s1-live/run001'
e5 = source/'e5/prepared/profile.json'
mini = source/'mmini/prepared/profile.json'
runs = Path('.rag-runs')
def invoke(*args):
    from rag_package.__main__ import main
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(list(map(str,args)))
    with (E/'practice.jsonl').open('a') as stream:
        stream.write(json.dumps(dict(args=list(map(str,args)), code=code, stdout=buf.getvalue()),ensure_ascii=False)+'\n')
    if code != 0:
        raise RuntimeError(f'{args[0]}: {buf.getvalue()[-500:]}')
def query(method):
    build, out = ('bm25','preview') if method=='fixed' else ('e5',method)
    config = 'fixed.json' if method=='fixed' else f'handbook-{method}.json'
    flags = [] if method=='fixed' else ['--execute-retrieval']
    invoke('ask','--run',runs/build,'--config',config,'--question',Q,'--out',runs/out,*flags)

def prepare():
    from rag_package import embedding, reranker
    import rag_package
    assert Path(rag_package.__file__).is_relative_to(base/'env')
    lock=ROOT/'rag_package/requirements-retrieval.lock'
    versions=dict(re.findall(r'^([\w.-]+)==([^\s\\]+)',lock.read_text(),re.M))
    for name, version in versions.items():
        assert md.version(name)==version,name
    assert md.version('pypdf')=='6.21.2'
    for module, profile in [(embedding,e5),(reranker,mini)]:
        p=module.read_profile(profile)
        module.check_files(p)
        module.versions()
        assert p['timeout_seconds']<=300 and p['device']=='cpu' and p['batch_size']==1
    os.chdir(base)
    invoke('init','--out','practice')
    os.chdir(ws)
    audit=read(ROOT/'docs/planning/reviews/p032-s2d-input-audit.json')
    pdf=Path('documents/handbook.pdf')
    shutil.copyfile(ROOT/audit['source_pdf'],pdf)
    assert sha(pdf)==audit['source_pdf_sha256']
    invoke('snapshot','--sources','handbook-sources.json','--out',runs/'pdf')
    invoke('build','--snapshot',runs/'pdf','--config','fixed.json','--out',runs/'bm25')
    query('fixed')
    # Execute the same configuration snippet shipped in the installed handbook.
    os.environ['E5_PROFILE']=str(e5)
    snippet=Path('HANDBOOK.md').read_text().split("python - <<'PY'\n")[1].split('\nPY\n')[0]
    exec(snippet,{})
    for method in ('dense','hybrid'):
        invoke('retrieval-preview','--config',f'handbook-{method}.json')
    inputs=[e5,mini,pdf,Path('fixed.json'),Path('handbook-dense.json'),Path('handbook-hybrid.json'),Path('llm-local.json'),lock,Path(install['wheel']),Path(__file__),ROOT/'docs/verification/p032-s1/live_control.py']
    inputs.extend(p for p in (runs/'pdf').rglob('*') if p.is_file())
    save(E/'freeze.json',dict(question=Q,inputs={str(p.resolve()):sha(p) for p in inputs},sdk=versions,workers=['index','dense','hybrid','rerank'],max_pairs=20,retries=0,wall_seconds=7200,rss_gib=4,generation=0))

def live():
    from rag_package.owned_worker import execution_scope
    from rag_package.ui_registry import atomic_json
    control=runpy.run_path(str(ROOT/'docs/verification/p032-s1/live_control.py'))
    control['Control'].before_spawn.__globals__['LIMITS']={'embedding_full':3,'reranker_full':1}
    os.chdir(ws)
    frozen=read(E/'freeze.json')
    assert all(sha(p)==v for p,v in frozen['inputs'].items())
    ledger=E/'ledger.json'
    with ledger.open('x') as stream:
        json.dump(dict(status='ready',active=None,jobs=[],started_at=None,reservations={'embedding_full':0,'reranker_full':0},reranker_full_pairs=0),stream)
    c=control['Control'](ledger)
    def job(label,fn,pairs=0):
        assert label==frozen['workers'][len(c.state['jobs'])] and 0<=pairs<=20
        with c.job(label,'reranker_full' if pairs else 'embedding_full',pairs) as row:
            fn()
            assert row['workers_started']==1 and row['observation']['resume_safe']
    with execution_scope(c):
        job('index',lambda:invoke('build','--snapshot',runs/'pdf','--config','handbook-dense.json','--out',runs/'e5','--execute-retrieval'))
        for method in ('dense','hybrid'):
            job(method,lambda:query(method))
        invoke('candidates','--build',runs/'e5','--result',runs/'hybrid','--question-id','first','--n','20','--out',runs/'candidates')
        for mode in ('off','on'):
            args=['rerank','--candidates',runs/'candidates','--method','none' if mode=='off' else 'cross-encoder','--top-k','5','--context-budget-chars','4000','--out',runs/mode]
            if mode=='on':
                job('rerank',lambda:invoke(*args,'--profile',mini,'--execute-reranking'),20)
            else:
                invoke(*args)
            invoke('answer-from-rerank','--run',runs/mode,'--llm-config','llm-local.json','--out',runs/('context-'+mode))
    c.state['status']='complete'
    c.save()

if __name__=='__main__':
    assert sys.executable==install['python']
    (prepare if sys.argv[1]=='prepare' else live)()
