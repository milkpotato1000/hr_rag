"""Model-free rank audit using exact document intervals and independent RRF arithmetic."""
import os,sys
from pairs import read,save,S4,E,install,new,old,ws,question

def main():
    from rag_package import candidates,reranking
    from pypdf import PdfReader
    expected=read(E/'inputs.json')
    baseline=read(S4/'ranks.json')
    full=baseline['full_clause'];key=baseline['deadline']
    page=' '.join(PdfReader(ws/'documents/handbook.pdf').pages[0].extract_text().split())
    assert full in page
    text=(old/'pdf/handbook/canonical.txt').read_text()
    start=text.index(full)
    cand,_,chunks=candidates.load(old/'candidates')
    assert read(new/'index/chunks.json')==chunks
    corpus={c['chunk_id']:c for c in chunks}
    def summarize(ranking,contexts=None):
        ids=[x['chunk_id'] for x in ranking]
        assert len(ids)==len(set(ids))
        details=[]
        for rank,cid in enumerate(ids,1):
            c=corpus[cid]
            assert text[c['start']:c['end']]==c['text']
            details.append(dict(rank=rank,id=cid,interval=[c['start'],c['end']],pages=[p['page'] for p in c['pages']],
                                deadline=c['start']<=start and c['end']>=start+len(key),
                                full=c['start']<=start and c['end']>=start+len(full)))
        def first(field):
            return next((v['rank'] for v in details if v[field]),None)
        result=dict(deadline=first('deadline'),full=first('full'),ranks=details)
        if contexts is not None:
            assert [x['chunk_id'] for x in contexts]==ids[:5]
            result.update(delivered=details[:5],chars=sum(len(c['text']) for c in contexts))
        return result
    variants={}
    for model,folder,idx in [('e5',old/'hybrid',old/'e5'),('bge',new/'hybrid',new/'index')]:
        r=read(folder/'result.json');index=read(idx/'index.json')
        assert r['question']==question and r['generation_requests']==0
        assert r['source_fingerprint']==expected['source'] and r['chunk_fingerprint']==expected['chunks']
        assert r['index_fingerprint']==index['fingerprint'] and index['identity']['embedding']==expected['models'][model]
        bm=r['retrieval_trace']['bm25'];dense=r['retrieval_trace']['dense']
        scores={}
        for rows in (bm,dense):
            for rank,row in enumerate(rows,1):
                cid=row['chunk_id'];scores[cid]=scores.get(cid,0)+1/(60+rank)
        fused=[dict(chunk_id=cid) for cid in sorted(scores,key=lambda cid:(-scores[cid],cid))]
        assert [x['chunk_id'] for x in fused[:5]]==[x['chunk_id'] for x in r['candidates']]
        if model=='e5':
            assert [x['chunk_id'] for x in fused[:20]]==[x['chunk_id'] for x in cand['rows']]
            original_bm=bm
        else:assert bm==original_bm
        variants[model]=dict(index=index['fingerprint'],bm25=summarize(bm),dense=summarize(dense),
                             hybrid=summarize(fused[:20],r['contexts']))
    assert variants['e5']['index']!=variants['bge']['index']
    reranks={}
    for label,folder in [('off',old/'off'),('mmini',old/'on'),('bge-reranker',new/'reranked')]:
        r,parent,_,_=reranking.load(folder)
        assert parent['rows']==cand['rows'] and r['candidate_fingerprint']==expected['candidates']
        assert r['question']==question and r['status']=='complete' and r['top_k_limit']==5 and r['context_budget_chars']==4000
        if label!='off':
            assert r['work']['execution_kind']=='local_hf' and r['work']['pairs']==20 and r['profile_identity']==expected['models'][label]
        reranks[label]=summarize(r['selection']['ranking'],r['selection']['contexts'])
    save(E/'comparison.json',dict(question=question,deadline=key,full=full,page=1,interval=[start,start+len(full)],
                                  candidate_fingerprint=expected['candidates'],chunk_count=len(chunks),embedding=variants,rerank=reranks))
if __name__=='__main__':
    if sys.executable!=install['python']:
        os.execv(install['python'],[install['python'],__file__])
    main()
