"""Bounded P017 verification against the already running loopback server; no LLM fresh call."""
import json,time,uuid,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parent
URL='http://127.0.0.1:8003'
def api(path,body=None):
    request=urllib.request.Request(URL+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=120) as r:return json.load(r)
def job(kind,body):
    value=api('/api/'+kind+'-jobs',{**body,'request_id':'p017-'+uuid.uuid4().hex})
    for _ in range(120):
        value=api('/api/jobs/'+value['job_id'])
        if value['status'] not in ('QUEUED','RUNNING'):break
        time.sleep(.5)
    assert value['status']=='SUCCEEDED',value
    return value

def main():
    state=api('/api/corpora');assert not any(j['status'] in ('QUEUED','RUNNING') for j in state['jobs'])
    before=state['ledger'];results={}
    jobs=[]
    for method in ('fixed','semantic'):
        cfg=dict(method=method,size_chars=600,overlap_chars=100 if method=='fixed' else 40)
        if method=='semantic':cfg['distance_threshold']=.3
        j=job('chunk',dict(corpus_id='source-v4',config=cfg,fresh=True));jobs.append(j);rid=j['result']['run_id'];results[method]=rid
        r=api('/api/runs/'+rid);assert r['statistics']['coverage_with_skipped']==38582
        assert max(r['statistics']['base_lengths'])<=600
        if method=='fixed':assert r['statistics']['max']==600
        for retriever in ('bm25','dense'):jobs.append(job('index',dict(chunk_run_id=rid,retriever=retriever)))
        replay=job('chunk',dict(corpus_id='source-v4',config=cfg,fresh=False));assert replay['result']['run_id']==rid and replay['result']['replayed']
        assert replay['result']['usage_delta']['llm_requests']==replay['result']['usage_delta']['embedding_items']==0
        jobs.append(replay)
    comparisons=[]
    state=api('/api/corpora');qid=next(q['query_id'] for q in state['questions'] if q['question']=='생일 휴가의 자격과 신청 기한, 사용 기간을 함께 알려 주세요.')
    for retriever in ('bm25','dense'):
        for budget in (1,1600,8000,24000):
            c=api('/api/search-comparisons',dict(a_run_id=results['fixed'],b_run_id=results['semantic'],retriever=retriever,top_k=5,budget_chars=budget,query_id=qid))['data']
            for r,rid in zip(c['results'],results.values()):
                assert r['ranking']['chunk_run_id']==rid and len(r['hits'])<=5
                assert r['budget']['used_chars']<=budget and r['budget']['candidate_count']<=20
                assert sum(len(h['text']) for h in r['budget']['hits'])==r['budget']['used_chars']
                assert [h['chunk_id'] for h in r['budget']['hits']]==r['budget']['selected']
            comparisons.append(c)
    after=api('/api/corpora')['ledger'];assert after['llm_requests']==before['llm_requests']
    summary=dict(status='PASS',runs=results,jobs=jobs,comparisons=comparisons,ledger_before=before,ledger_after=after)
    (ROOT/'live-verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',runs=results,comparisons=len(comparisons),llm_calls=0),ensure_ascii=False))
if __name__=='__main__':main()
