"""Inspect the installed artifact without a provider or additional inference."""
import json
import os
from pathlib import Path
import subprocess
import sys

E=Path(__file__).resolve().parent
def read(path):
    return json.loads(path.read_text())

install=read(E/'installation.json')
python=Path(install['python'])
if Path(sys.executable)!=python:
    os.execv(python,[str(python),'-I',__file__])
from rag_package import chunk_artifact
from rag_package.bm25 import BM25Index

base=Path(install['base'])
result=read(E/'result.json')
record=read(Path(result['invocation_path'])/'invocation.json')['windows'][0]
response=record['response'] or {}
ledger=read(E/'ledger.json')
assert len(ledger['requests'])==1 and ledger['automatic_retries']==0
review={'status':result['status'],'dispatches':result['work']['dispatches'],
        'provider_status':response.get('status'),'identity':response.get('identity_verification'),
        'usage':response.get('usage'),'provider_error':response.get('error'),
        'selected':record.get('selected_candidate_id'),'chunks':None,'retrieval':None}
if result['status']=='ready':
    target=base/'selected'
    replay=subprocess.run([base/'env/bin/rag-lab','chunk-replay','--run',target],cwd=base,capture_output=True,text=True,check=True)
    assert json.loads(replay.stdout)['model_calls']==0
    saved,docs,chunks,maps=chunk_artifact.load(target)
    frozen=read(E/'frozen.json')
    candidate=next(c for c in frozen['candidates'] if c['id']==review['selected'])
    assert candidate['pieces']==[{k:c[k] for k in ('start','end','text')} for c in chunks]
    assert ''.join(c['text'] for c in chunks)==frozen['source_text']
    assert all([p['page'] for p in c['pages']]==[1] for c in chunks)
    data=read(E.parent/'p032-s16/verified.json')
    corpus={c['chunk_id']:c for c in chunks}
    _,hits=BM25Index(corpus).search(data['question'],5)
    ranks=[i for i,h in enumerate(hits,1) if data['quote'] in corpus[h['chunk_id']]['text']]
    review.update(chunks=chunks,source_chars=len(frozen['source_text']),retrieval={
        'question':data['question'],'quote':data['quote'],'page':1,'ranks_with_quote':ranks,'hits':hits})
(E/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
