"""Check source spans independently of the chunker and read saved BM25 ranks."""
import json
import shutil
from pathlib import Path
E=Path(__file__).resolve().parent
def read(p):
    return json.loads(p.read_text())
runs=Path(read(E/'installation.json')['base'])/'practice/.rag-runs'
s=(runs/'pdf/handbook/canonical.txt').read_text()
target=read(E/'target.json')
start,stop=target['start'],target['end']
summary=[]
paths=[]
for i,m in enumerate(('fixed','recursive','structure'),1):
    chunks_dir=runs/('handbook-chunk-'+m)
    chunks=read(chunks_dir/'chunks.json')
    result=read(runs/f'handbook-chunk-compare/config-{i}/answers/deadline/result.json')
    cfg=result['effective_settings']['retrieval']
    assert (cfg['method'],cfg['candidate_k'],cfg['top_k'],cfg['context_budget_chars'])==('bm25',20,5,4000)
    assert result['status']=='preview' and result['generation_requests']==0
    assert read(chunks_dir/'chunk.json')['work']['boundary_model_jobs']==0
    ranks={r['chunk_id']:r['rank'] for r in result['retrieval_trace']['bm25']}
    selected={c['chunk_id'] for c in result['contexts']}
    assert selected=={c['chunk_id'] for c in result['candidates']}
    boundaries=[]
    for c in chunks:
        a,b,body=c['start'],c['end'],c['text']
        assert s[a:b]==body and len(body)<=400
        if a<stop and b>start:
            boundaries.append(dict(chunk_id=c['chunk_id'],start=a,end=b,source_excerpt=s[max(a,start-45):min(b,stop+45)],pages=c['pages'],heading_path=c['heading_path'],bm25_rank=ranks.get(c['chunk_id']),selected=c['chunk_id'] in selected,deadline=a<=start and b>=target['deadline_end'],whole=a<=start and b>=stop))
    paths.append([(c['start'],c['end']) for c in chunks])
    detection=read(chunks_dir/'coverage.json')['detection']
    item=dict(method=m,chunks=len(chunks),source=result['source_fingerprint'],detection=detection,boundaries=boundaries,
              headings=sorted({h for c in chunks for h in c['heading_path']}))
    summary.append(item)
    print(m,len(chunks),detection,[(r['start'],r['end'],r['bm25_rank'],r['deadline'],r['whole'],r['selected']) for r in boundaries],item['headings'][:3])
assert len({r['source'] for r in summary})==1
print('recursive=structure boundaries',paths[1]==paths[2])
(E/'boundaries.json').write_text(json.dumps({'methods':summary,'recursive_structure_same_spans':paths[1]==paths[2]},ensure_ascii=False,indent=2)+'\n')
report=runs/'handbook-chunk-report'
assert read(report/'comparison.json')==read(runs/'handbook-chunk-compare/comparison.json')
shutil.copyfile(report/'report.html',E/'replay.html')
