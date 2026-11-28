"""Independent checks of saved source slices, provenance and ranks."""
from pathlib import Path
import json,shutil
E=Path(__file__).resolve().parent
def read(path):
    return json.loads(path.read_text())
runs=Path(read(E/'installation.json')['base'])/'practice/.rag-runs'
s=(runs/'pdf/handbook/canonical.txt').read_text()
t=read(E/'target.json')
rows=[]
for index,name in enumerate(('handbook-chunk-structure','handbook-hierarchy'),1):
    folder=runs/name
    chunks=read(folder/'chunks.json')
    result=read(runs/f'heading-compare/config-{index}/answers/deadline/result.json')
    assert result['status']=='preview' and result['generation_requests']==0
    cfg=result['effective_settings']['retrieval']
    assert [cfg[k] for k in ('method','candidate_k','top_k','context_budget_chars')]==['bm25',20,5,4000]
    ranks={r['chunk_id']:r['rank'] for r in result['retrieval_trace']['bm25']}
    selected={c['chunk_id'] for c in result['contexts']}
    paths=set()
    hits=[]
    for c in chunks:
        a,b=c['start'],c['end']
        assert c['text']==s[a:b] and b-a<=400
        for p in c['pages']:
            page=(runs/f"pdf/handbook/page-{p['page']}.txt").read_text()
            assert page[p['page_start']:p['page_end']]==s[p['canonical_start']:p['canonical_end']]
        paths.add(tuple(c['heading_path']))
        if a<=t['start'] and b>=t['deadline_end']:
            hits.append(dict(id=c['chunk_id'],start=a,end=b,path=c['heading_path'],whole=b>=t['end'],rank=ranks.get(c['chunk_id']),selected=c['chunk_id'] in selected))
    row=dict(method=name,chunks=len(chunks),detection=read(folder/'coverage.json')['detection'],paths_by_depth=[sum(len(p)==n for p in paths) for n in (1,2,3)],hits=hits,toc_paths=[list(p) for p in {tuple(c['heading_path']) for c in chunks if c['start']<209}])
    print(row);rows.append(row)
assert len(rows[1]['hits'][0]['path'])==3 and rows[1]['toc_paths']==[[]]
(E/'ranks.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n')
shutil.copyfile(runs/'heading-report/report.html',E/'replay.html')
