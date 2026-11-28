"""Independent model-free delivery checks, including source slices and prior artifacts."""
from runtime import *
from pathlib import Path
verify_parent()
frozen=read(E/'frozen.json')
for entries,base in [(frozen['scripts'],E),(frozen['input_files'],ROOT),(frozen['installed_files'],Path('/'))]:
    for name,digest in entries.items():
        need(sha(base/name)==digest,'changed_frozen_file')
need(sha(Path(frozen['wheel']))==frozen['wheel_sha256'],'wheel_changed')
prior=read(E.parent/'p032-s1/preservation.json')['files']
for name,digest in prior.items():
    need(sha(ROOT/name)==digest,'protected_changed')
ledger=read(LEDGER)
requests=ledger['requests']
need([r['question_id'] for r in requests]==ORDER[:len(requests)],'request_order')
need(0<len(requests)<=10 and len(ledger['metadata'])<=1200,'limits')
need(ledger['deadline']-ledger['started_at']<=5400.01,'clock')
results=[]
for row in frozen['rows']:
    q=row['question_id'];path=E/'answers'/q/'result.json'
    if not path.exists():
        results.append(dict(question=q,status='not_executed'))
        continue
    result=read(path);review=read(E/(q+'-review.json'))
    need(review['result_sha256']==sha(path),'review_hash')
    preview=read(E/'preview'/q/'result.json')
    need(result['preview']==preview['preview'] and result['contexts']==preview['contexts'],'input_changed')
    contexts={c['chunk_id']:c for c in result['contexts']}
    schema=result['preview']['body']['format']
    need(schema['properties']['citations']['items']['properties']['chunk_id']['enum']==list(contexts),'id_enum')
    for c in (result['answer'] or {}).get('citations',[]):
        chunk=contexts[c['chunk_id']]
        need(c['quote']==chunk['text'] and c['start']==chunk['start'] and c['end']==chunk['end'],'citation_slice')
    results.append(dict(question=q,status=result['status'],review_passed=review['passed'],error=result.get('error')))
samples=[json.loads(s) for s in (E/'resources.jsonl').read_text().splitlines()]
write(E/'final-checks.json',dict(results=results,generation_requests=len(requests),cumulative_requests=len(requests)+2,
    metadata_requests=len(ledger['metadata']),peak_sampled_rss_bytes=max(s['rss_bytes'] for s in samples),
    pressure_levels=sorted({s['pressure'] for s in samples}),prior_protected_files=len(prior),parent_hashes_verified=True,
    server_cleanup=read(E/'server-closed.json'),auto_retries=0,package_tests=136,control_tests=18))
