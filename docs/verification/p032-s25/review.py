"""Read only the completed run; check reuse, source slices and duplicate protection."""
import json,os,subprocess,sys
from experiment import E,ws,base,python,out,read,write,rt,frozen

if sys.executable!=str(python):
    os.execv(python,[str(python),__file__])
from rag_package.llm.core import hash_json
from rag_package.storage import verify
assert frozen()==read(E/'frozen.json')
verify(out/'answer','answer')
result=read(out/'answer/result.json')
prior=read(ws/'evidence/result.json')
printed=read(E/'cli.log')
assert result['index_fingerprint']==prior['index_fingerprint'] and result['contexts']==prior['contexts']
assert printed['answer']==result['answer'] and printed['question']==prior['question']
assert result['generation_requests']==1 and result['provider_result']['identity_verification']['status']=='verified'
ledger=read(E/'ledger.json')
assert ledger['status']=='complete' and len(ledger['requests'])==1 and ledger['automatic_retries']==0
assert ledger['requests'][0]['body_hash']==hash_json(result['preview']['body'])==frozen()['body_hash']
canonical=(ws/'snapshot/handbook/canonical.txt').read_text()
page=(ws/'snapshot/handbook/page-1.txt').read_text()
contexts={c['chunk_id']:c for c in prior['contexts']}
refs=[]
for ref in result['answer']['citations']:
    c=contexts[ref['chunk_id']]
    assert ref['quote']==c['text']==canonical[ref['start']:ref['end']]
    for p in ref['pages']:
        src=(ws/f"snapshot/handbook/page-{p['page']}.txt").read_text()
        assert canonical[p['canonical_start']:p['canonical_end']]==src[p['page_start']:p['page_end']]
    refs.append(dict(id=ref['chunk_id'],pages=[p['page'] for p in ref['pages']],start=ref['start'],end=ref['end'],
                     source=ref['quote'],supports_deadline='사용 3영업일 전까지 휴가 시스템에서 신청' in ref['quote']))
before=rt.sha(out/'answer/result.json')
proc=subprocess.run(['../env/bin/rag-lab','first-answer','--execute'],cwd=ws,capture_output=True,text=True,check=False)
assert proc.returncode==2 and json.loads(proc.stdout)['error']['code']=='output_exists' and before==rt.sha(out/'answer/result.json')
assert frozen()==read(E/'frozen.json') and read(E/'server-closed.json')['listener_closed']
write(E/'review.json',dict(answer=result['answer']['answer'],status=result['status'],citations=refs,question=result['question'],
    contexts_equal=True,index_fingerprint=result['index_fingerprint'],snapshot_index_pdf_and_preview_unchanged=True,
    duplicate_error='output_exists',initial_search_generation=0,generation_calls=1,retries=0,unloaded=True))
