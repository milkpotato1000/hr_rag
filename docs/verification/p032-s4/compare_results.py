"""Read saved ranks and verify direct BD-03 evidence against PDF page 1."""
import json
from pathlib import Path
from pypdf import PdfReader

E = Path(__file__).resolve().parent
def read(path):
    return json.loads(path.read_text())
ws = Path(read(E/'installation.json')['base'])/'practice'
runs = ws/'.rag-runs'
sentence = '생일 특별휴가는 사용 3영업일 전까지 휴가 시스템에서 신청하고 팀장의 승인을 받아야 한다.'
deadline = sentence.split('하고')[0]
page = ' '.join(PdfReader(ws/'documents/handbook.pdf').pages[0].extract_text().split())
assert sentence in page
corpus = read(runs/'bm25/chunks.json')
assert corpus == read(runs/'e5/chunks.json')
by_id = {row['chunk_id']:row for row in corpus}
def ids(rows):
    return [r['chunk_id'] for r in rows]
def describe(rows, contexts):
    selected=ids(contexts)
    assert selected==ids(rows[:5])
    result=[]
    for rank,row in enumerate(rows,1):
        chunk=by_id[row['chunk_id']]
        text=' '.join(chunk['text'].split())
        result.append(dict(rank=rank,id=row['chunk_id'],pages=[p['page'] for p in chunk['pages']],deadline=deadline in text,full_clause=sentence in text,selected=row['chunk_id'] in selected,score=row.get('score',row.get('reranker_score')),original_rank=row.get('original_rank')))
    return result
results={}
for mode in ('preview','dense','hybrid'):
    r=read(runs/mode/'result.json')
    assert r['question']==read(E/'freeze.json')['question'] and r['generation_requests']==0
    assert r['effective_settings']['retrieval']['context_budget_chars']==4000
    results[mode]=describe(r['candidates'],r['contexts'])
cand=read(runs/'candidates/candidates.json')
assert cand['actual_n']==20
for mode in ('off','on'):
    r=read(runs/mode/'result.json')
    assert r['candidate_fingerprint']==cand['candidate_fingerprint']
    assert r['status']=='complete' and r['top_k_limit']==5 and r['context_budget_chars']==4000
    ranked=r['selection']['ranking']
    assert sorted(ranked,key=lambda x:x['original_rank'])==[next(v for v in ranked if v['chunk_id']==k) for k in ids(cand['rows'])]
    for row,original in zip(sorted(ranked,key=lambda x:x['original_rank']),cand['rows']):
        assert all(row[k]==v for k,v in original.items())
    preview=read(runs/('context-'+mode)/'result.json')
    assert preview['contexts']==r['selection']['contexts'] and preview['generation_requests']==0
    results[mode]=describe(ranked,preview['contexts'])
assert [r['id'] for r in results['hybrid']]==[r['id'] for r in results['off'][:5]]
(E/'ranks.json').write_text(json.dumps(dict(question=cand['question'],source=cand['source_fingerprint'],chunk_count=len(corpus),chunk_fingerprint=cand['chunk_fingerprint'],candidate_fingerprint=cand['candidate_fingerprint'],deadline=deadline,full_clause=sentence,results=results),ensure_ascii=False,indent=2)+'\n')
for name, rows in results.items():
    print(name,[(r['rank'],r['pages'],r['full_clause']) for r in rows if r['deadline']])
