"""Check the live UI job and its citations against the installed PDF snapshot."""
from pathlib import Path
import json
import shutil
import sys
E = Path(__file__).resolve().parent
sys.path.insert(0, str(E.parent/'p032-s8'))
from control import read, write, transact
setup = read(E/'setup.json')
ws = Path(setup['practice'])
ui = ws/'.rag-runs/ui'
jobs = [read(p) for p in (ui/'jobs').glob('*.json')]
preview, live = sorted(jobs, key=lambda j: j['request']['execute'])
assert preview['input_fingerprint'] == live['input_fingerprint']
assert preview['dispatch_attempted'] is False
dispatch = read(E/'dispatch.json')
assert live['request']['question'] == dispatch['question'] == setup['question']
out = ui/'artifacts'/live['id']/'result'
result = read(out/'answer/result.json')
assert result['question'] == setup['question']
contexts = {c['chunk_id']: c for c in dispatch['contexts']}
source = (out/'snapshot/handbook/canonical.txt').read_text()
page = (out/'snapshot/handbook/page-1.txt').read_text()
assert setup['quote'] in page
answer = result['answer'] or {}
citations = []
for citation in answer.get('citations', []):
    text = citation['quote']
    assert contexts[citation['chunk_id']]['text'] == text == source[citation['start']:citation['end']]
    citations.append(dict(chunk_id=citation['chunk_id'], pages=citation['pages'],
                          source_match=True, contains_rule=setup['quote'] in text))
provider = result['provider_result']
technical = provider['status'] == 'complete' and provider['identity_verification']['status']=='verified'
observed = read(E/'first-observation.json')
with transact(E/'ledger.json') as c:
    if technical:
        c.finish('first',True,observed['unloaded_observed'],True)
        c.s['status']='complete'
    else:
        c.halt(result['error'])
for filename,path in [('result.json',out/'answer/result.json'),('preview-job.json',ui/'jobs'/(preview['id']+'.json')),('live-job.json',ui/'jobs'/(live['id']+'.json'))]:
    shutil.copyfile(path,E/filename)
write(E/'review.json',dict(job=live['id'],question=setup['question'],status=result['status'],
     answer=answer.get('answer'),elapsed_ms=provider['elapsed_ms'],citations=citations,
     bd03_context_ranks=[i for i,c in enumerate(dispatch['contexts'],1) if setup['quote'] in c['text']],
     generation_requests=result['generation_requests'],source_quote=setup['quote']))
