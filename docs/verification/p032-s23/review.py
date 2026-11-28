"""Compare saved dispatch bodies, source slices, and final citations without inference."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parent
S22=ROOT.parent/'p032-s22'
def read(path):
    return json.loads(path.read_text())
def fingerprint(value):
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def inspect(label):
    folder=ROOT/label
    result=read(folder/'result.json')
    expected=read(S22/'results.json')[label]
    assert result['contexts']==expected['contexts'] and result['retrieval_trace']['bm25']==expected['ranking']
    planned=read(folder/'planned.json')
    dispatch=read(folder/'dispatch.json')
    ledger=read(folder/'ledger.json')
    assert planned['body']==result['preview']['body']
    assert fingerprint(planned['body'])==dispatch['body_hash']==ledger['requests'][0]['body_hash']
    assert dispatch['user_payload']==json.loads(planned['body']['messages'][-1]['content'])
    assert len(ledger['requests'])==result['generation_requests']==1 and ledger['automatic_retries']==0
    assert read(folder/'first-observation.json')['unloaded_observed'] and read(folder/'server-closed.json')['listener_closed']
    by_id={c['chunk_id']:c for c in result['contexts']}
    base=Path(read(S22/'installation.json')['base'])
    source=(base/'practice/size-lab-pdf/handbook/canonical.txt').read_text()
    citations=[]
    answer=result['answer']
    for citation in (answer or {}).get('citations',[]):
        c=by_id[citation['chunk_id']]
        assert c['text']==citation['quote']==source[c['start']:c['end']]
        assert c['pages']==citation['pages']
        citations.append(dict(chunk_id=c['chunk_id'],start=c['start'],end=c['end'],pages=[p['page'] for p in c['pages']],
                         deadline_support='사용 3영업일 전까지 휴가 시스템에서 신청' in c['text'],
                         approval_support='팀장의 승인을 받아야 한다' in c['text'],quote=c['text']))
    return dict(status=result['status'],answer=(answer or {}).get('answer'),citations=citations,error=result.get('error'),
                provider_status=result['provider_result']['status'],tokens=result['usage'],
                context_chars=planned['context_chars'],context_count=len(by_id),question=result['question'])
if __name__=='__main__':
    rows={label:inspect(label) for label in ('baseline','budget')}
    (ROOT/'comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
