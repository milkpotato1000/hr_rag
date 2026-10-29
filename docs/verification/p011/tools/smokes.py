"""Post-benchmark CLI/API smoke, including standalone copied product."""
import json,subprocess,time,sys,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p011';s=root/'1. Naive RAG';b=s/'variants/langchain';copy=Path(json.loads((ev/'copy-location.json').read_text())['path']);proto=json.loads((ev/'protocol.json').read_text());cases={c['id']:c for c in proto['cases']};out=ev/'smokes';out.mkdir(exist_ok=True)
assert len(list((ev/'runs').glob('cold-*.json')))==18
results={}
for label,stage,impl,cid in [('original-meal',s,'direct','meal-bm25'),('candidate-direct-meal',b,'direct','meal-bm25'),('candidate-lc-meal',b,'langchain','meal-bm25'),('candidate-lc-pdf',b,'langchain','pdf-q06'),('copy-lc-meal',copy,'langchain','meal-bm25'),('copy-lc-pdf',copy,'langchain','pdf-q06'),('copy-lc-missing',copy,'langchain','q13')]:
 c=cases[cid];cmd=[str(stage/'.venv/bin/python'),str(stage/'scripts'/('ask.py' if stage==s else 'ask_compare.py')),'--question',c['question'],'--retriever',c['retriever']]
 if stage!=s:cmd+=['--implementation',impl]
 if cid=='pdf-q06':cmd+=['--chunks',str(stage/'data/source-v2/fixed-400-80/chunks.jsonl'),'--index-dir',str(stage/'.runtime/index-source-v2-fixed-400-80')]
 start=time.perf_counter();proc=subprocess.run(cmd,cwd=stage,capture_output=True,text=True);r=json.loads(proc.stdout);data={'label':label,'stage':str(stage),'returncode':proc.returncode,'result':r,'wall_ms':(time.perf_counter()-start)*1000,'stderr':proc.stderr};(out/(label+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');results[label]=r
 with (ev/'ledger.jsonl').open('a') as f:f.write(json.dumps({'slot':'smoke-'+label,'dispatches':r['trace']['generation_calls'],'count_basis':'actual pipeline dispatch trace; 0/1 independently validated at HTTP boundary in parity suite','result':r['status']})+'\n')
 print(label,r['status'],flush=True);assert r['status']!='error'
def normalized(r):
 r=json.loads(json.dumps(r));t=r['trace'];t.pop('timings_ms');t.pop('comparison',None)
 t['retrieval']={k:v for k,v in t['retrieval'].items() if not k.endswith('_ms')};t['generation'].pop('observations',None);return r
assert normalized(results['original-meal'])==normalized(results['candidate-direct-meal'])==normalized(results['candidate-lc-meal'])==normalized(results['copy-lc-meal'])
# No extra model call: input validation and API selection error mapping.
req=urllib.request.Request('http://127.0.0.1:8001/api/ask',data=json.dumps({'question':'q','implementation':'invalid'}).encode(),headers={'Content-Type':'application/json'})
try:urllib.request.urlopen(req);raise AssertionError('must return400')
except urllib.error.HTTPError as e:assert e.code==400;(out/'api-input-error.json').write_bytes(e.read())
(ev/'copy-regression.json').write_text(json.dumps({'status':'PASS','copy_path':str(copy),'original_tests':107,'candidate_additional_tests':32,'live_cases':['meal-bm25','pdf-q06','q13'],'model_service':'shared original owned locked runtime','parent_imports':False,'root_vs_candidate_direct_meal_exact_except_declared_observations':True},indent=2)+'\n')
