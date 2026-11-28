"""Replay the installed general pipeline and verify page ranges and frozen inputs."""
from pathlib import Path
import json
import hashlib
import os
import subprocess
import sys

E=Path(__file__).resolve().parent
ROOT=E.parents[2]
def read(path):
    return json.loads(path.read_text())
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

install=read(E.parent/'p032-s18/installation.json')
python=Path(install['python'])
if Path(sys.executable)!=python:
    os.execv(python,[str(python),'-I',__file__])
from rag_package.llm.core import hash_json
ws=Path(install['base'])/'s19-practice'
actual=ws/'actual'
plan=read(E/'planned.json')
result=read(actual/'answer/result.json')
stored=read(actual/'pipeline.json')
cli=python.parent/'rag-lab'
stdout=subprocess.check_output([cli,'pipeline-replay','--run',actual],cwd=ws,text=True)
assert json.loads(stdout)==stored
review_dir=ROOT/'docs/planning/reviews'
approval=read(review_dir/'P013-human-approval.json')
manifest=ROOT/approval['review_manifest']
canonical=actual/'snapshot/handbook/canonical.txt'
assert approval['status']=='APPROVED' and 'gt09' in approval['scope']['questions']
assert sha(manifest)==approval['review_manifest_sha256']
assert sha(canonical)==read(manifest)['source_canonical_sha256']
run001=ROOT/'evaluation/project_b/preparation/artifacts/run001'
assert sha(actual/'snapshot/handbook/original.pdf')==read(run001/'p007-inputs.json')['source_pdf_sha256']
text=canonical.read_text()
ledger=read(E/'ledger.json')
assert len(ledger['requests'])==1 and ledger['automatic_retries']==0
assert sha(review_dir/'P013-human-review.md')==plan['inputs']['human_review']
for key,h in plan['inputs'].items():
    if key not in ('human_review','s11_result'):assert sha(ws/key)==h
assert sha(E.parent/'p032-s11/result.json')==plan['inputs']['s11_result']
dispatch=read(E/'dispatch.json')
assert dispatch['body_hash']==hash_json(plan['body'])==ledger['requests'][0]['body_hash']
assert result['contexts']==plan['contexts']
for chunk,sent in zip(result['contexts'],dispatch['user_payload']['contexts'],strict=True):
    assert text[chunk['start']:chunk['end']]==chunk['text']==sent['text']
    assert chunk['chunk_id']==sent['chunk_id']
    for p in chunk['pages']:
        page=actual/f"snapshot/handbook/page-{p['page']}.txt"
        assert page.read_text()[p['page_start']:p['page_end']]==text[p['canonical_start']:p['canonical_end']]
provider=result.get('provider_result') or {}
summary=dict(status=result['status'],answer=result.get('answer'),provider_status=provider.get('status'),
             finish_reason=provider.get('finish_reason'),usage=provider.get('usage'),error=result.get('error'),
             citation_validation=result.get('citation_validation'),model_calls=1,replay_calls=0,
             canonical_sha256=sha(canonical),canonical_chars=len(text),approved_gt09=True,
             verified_contexts=len(result['contexts']),identity=provider.get('identity_verification'))
if result['status']=='abstained':
    assert summary['answer']['citations']==[] and provider['status']=='complete'
(E/'review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
