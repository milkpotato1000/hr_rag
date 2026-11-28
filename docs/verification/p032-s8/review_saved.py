"""Independent PDF provenance, completion counters and offline CLI replay."""
from pathlib import Path
import hashlib,json,subprocess,sys
from pypdf import PdfReader

E=Path(__file__).resolve().parent
def read(path):
    return json.loads(path.read_text())
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
f=read(E/'frozen.json')
ws=Path(f['practice'])
run=ws/'.rag-runs/pipeline-live'
cli=Path(f['python']).with_name('rag-lab')
report=json.loads(subprocess.check_output([cli,'pipeline-replay','--run',run],text=True,cwd=ws))
assert read(run/'pipeline.json')==report
assert all(v=='complete' for v in report['stages'].values()) and report['generation_requests']==1
assert report['plan']['chunking']['heading_profile']=='handbook-v1'
chunks={r['chunk_id']:r for r in read(run/'chunks/chunks.json')}
ranked=read(run/'rerank/result.json')
search=read(run/'search/result.json')
answer=read(run/'answer/result.json')
assert search['generation_requests']==0 and search['effective_settings']['retrieval']['method']=='hybrid'
assert len(chunks)==177 and search['embedding_work']['queries']==1
assert read(run/'index/embedding-work.json')['documents']==177
assert ranked['work']['pairs']==20 and ranked['method']=='cross-encoder'
contexts=ranked['selection']['contexts']
assert [r['chunk_id'] for r in answer['contexts']]==[c['chunk_id'] for c in contexts]==read(E/'dispatch-context.json')['context_ids']
rawdoc=run/'snapshot/handbook'
pdf=PdfReader(rawdoc/'original.pdf')
source=(rawdoc/'canonical.txt').read_text()
audited=[]
for citation in answer['answer']['citations']:
    cid=citation['chunk_id']
    chunk=chunks[cid]
    index=next(i for i,r in enumerate(contexts,1) if r['chunk_id']==cid)
    assert all(citation[k]==chunk[k] for k in ('heading_path','pages','start','end','source_fingerprint','document_id'))
    assert citation['quote']==chunk['text']==source[chunk['start']:chunk['end']]
    for p in chunk['pages']:
        actual=pdf.pages[p['page']-1].extract_text()
        from rag_package.documents import normalize
        assert normalize(actual)[p['page_start']:p['page_end']]==source[p['canonical_start']:p['canonical_end']]
    audited.append(dict(id=cid,rank=index,path=chunk['heading_path'],pages=[p['page'] for p in chunk['pages']],start=chunk['start'],end=chunk['end'],quote=chunk['text']))
assert all(sha(p)==h for p,h in read(E/'parent-hashes.json').items())
verified=dict(stages=report['stages'],question=report['question'],answer=answer['answer']['answer'],
              citations=audited,generation_requests=report['generation_requests'],usage=answer['provider_result']['usage'],
              elapsed_ms=answer['provider_result']['elapsed_ms'],index_work=read(run/'index/embedding-work.json').get('jobs'),
              rerank_pairs=ranked['work']['pairs'],query_jobs=search['embedding_work']['jobs'],chunk_count=len(chunks),
              final_contexts=[dict(id=c['chunk_id'],path=c['heading_path'],before=c['original_rank'],after=c['rank']) for c in contexts],
              replay_model_requests=0)
(E/'verified.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(verified,ensure_ascii=False)[:1400])
