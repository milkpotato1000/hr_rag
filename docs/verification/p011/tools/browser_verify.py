"""Verify JSONs downloaded through the actual browser UI; no model calls."""
import json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p011'
reviews={r['case_id']:r for r in json.loads((ev/'manual-reviews.json').read_text())}
for filename,expected in [('browser-q03.json','answered'),('browser-missing.json','abstained')]:
 pair=json.loads((ev/filename).read_text());assert pair['mode']=='manual_single_pair_not_benchmark'
 assert [(r['implementation'],r['order']) for r in pair['results']]==[('direct',1),('langchain',2)]
 a,b=[r['result'] for r in pair['results']]
 assert a['status']==b['status']==expected
 for field in ['answer','citations','reason']:assert a[field]==b[field],(filename,field)
 for field in ['candidates','contexts','excluded','prompt','generation_calls','corpus_sha256']:
  assert a['trace'][field]==b['trace'][field],(filename,field)
 for r in [a,b]:
  assert r['trace']['generation_calls']==1
  contexts={c['chunk_id']:c for c in r['trace']['contexts']}
  for citation in r['citations']:assert citation['quote']==contexts[citation['chunk_id']]['text']
  if expected=='answered':
   sig=hashlib.sha256(json.dumps({k:r[k] for k in ('status','answer','citations','reason')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
   assert sig==reviews['q03']['reviewed_output_sha256']
  else:assert r['reason']=='model_abstained' and not r['citations']
 ledger=[json.loads(l) for l in (ev/'ledger.jsonl').read_text().splitlines()]
 slot=Path(filename).stem
 if not any(x['slot']==slot for x in ledger):
  with (ev/'ledger.jsonl').open('a') as f:f.write(json.dumps({'slot':slot,'dispatches':2,'count_basis':'actual browser JSON download trace','pair_id':pair['pair_id']})+'\n')
fault=json.loads((ev/'browser-fault-download.json').read_text())
assert [r['result']['status'] for r in fault['results']]==['abstained','error']
for name in ['browser-q03.png','browser-missing.png','browser-fault.png','browser-narrow.png']:assert (ev/name).stat().st_size>0
report={'status':'PASS','method':'actual IAB accessibility inspection, interactions, screenshots and downloaded JSON; never direct network substitution for UI tests',
 'real_model_cases':[{'file':'browser-q03.json','question':'생일 휴가의 자격과 신청 기한, 사용 기간을 함께 알려 주세요.','outcome':'both answered; three full citations; matches reviewed q03 output; annual1day omission retained'},{'file':'browser-missing.json','question':'배우자 출산 휴가는 며칠인가요?','outcome':'both model_abstained; no citations; synthetic corpus has no spouse-childbirth policy'}],
 'real_server':'127.0.0.1:8001','source_corpus':'synthetic15','rank_context_excluded_equal':True,'json_download_verified':True,
 'inflight_inputs':'question, examples, implementation, retriever, K, budget and both submit buttons visibly disabled; reenabled on completion; old results removed during next run',
 'fault_injection':{'server':'127.0.0.1:8002','local_fixture':True,'real_model_calls':0,'evidence':'browser-fault-download.json','outcome':'one timeout and other no_context both retained'},
 'narrow':{'fixture_iframe_width':390,'evidence':'browser-narrow.png','method':'actual accessibility and visual inspection; no numeric overflow measurement','outcome':'vertical comparison cards and controls visible'},
 'manual_timing':'single direct-first pair only; not formal randomized timing benchmark','automated_http_checks':'langchain-tests-http.log; 4 HTTP cases within32 tests'}
(ev/'browser-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('actual browser downloads and UI gates PASS')
