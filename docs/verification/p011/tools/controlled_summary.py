"""Overlay complete preregistered repair groups, retaining original failed reports."""
import runpy,json,hashlib,collections
from pathlib import Path
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p011';ns=runpy.run_path(str(Path(__file__).with_name('summarize.py')));stats=ns['stats'];metrics=ns['metrics'];reviews={r['case_id']:r for r in json.loads((ev/'manual-reviews.json').read_text())};affected={'q14','q03','q06'}
repairwarm=sorted((ev/'runs').glob('repair-warm-*.json'));repaircold=sorted((ev/'runs').glob('repair-cold-*.json'));assert len(repairwarm)==18 and len(repaircold)==18
selected=[]
for p in sorted((ev/'runs').glob('warm-*.json')):
 d=json.loads(p.read_text())
 if d['case_id'] in affected:p=ev/'runs'/('repair-'+p.name);d=json.loads(p.read_text())
 d['kind']='warm';selected.append(d)
for p in repaircold:
 d=json.loads(p.read_text());d['kind']='cold';selected.append(d)
assert len(selected)==138
for d in selected:
 r=d['result'];assert r['status']!='error',d['slot']
 v={k:r[k] for k in ('status','answer','citations','reason')};sig=hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False).encode()).hexdigest();assert sig==reviews[d['case_id']]['reviewed_output_sha256'],('manual review needed',d['slot'])
 if d['slot'].startswith('repair-'):assert abs(d['wall_clock_ms']-d['client_wall_ms'])<1000,('suspension',d['slot'])
# Verify the actual HTTP messages/serialized payload and quote bytes also after restart.
pairs=collections.defaultdict(dict)
for d in selected:pairs[d['kind'],d['case_id'],d['round']][d['implementation']]=d
for key,pair in pairs.items():
 a,b=[pair[k] for k in ('direct','langchain')]
 for field in ['candidates','contexts','excluded','context_chars','prompt','generation_calls','validation','citation_assembly','corpus_sha256']:
  assert a['result']['trace'].get(field)==b['result']['trace'].get(field),(key,field)
 for route in ['/api/chat','/api/embed']:
  assert [w['data'] for w in a['wire'] if w['url'].endswith(route)]==[w['data'] for w in b['wire'] if w['url'].endswith(route)],(key,route)
 for d in (a,b):
  t=d['result']['trace'];ctx={c['chunk_id']:c for c in t['contexts']};assert sum(w['url'].endswith('/api/chat') for w in d['wire'])==t['generation_calls']<=1
  for c in d['result']['citations']:assert c['quote'].encode()==ctx[c['chunk_id']]['text'].encode()
groups=collections.defaultdict(list)
for d in selected:groups[d['kind'],d['case_id'],d['implementation']].append(d)
summary=[]
for (kind,cid,impl),ds in groups.items():summary.append(dict(kind=kind,case_id=cid,implementation=impl,status_counts=dict(collections.Counter(d['result']['status'] for d in ds)),metrics={k:stats([metrics(d)[k] for d in ds]) for k in metrics(ds[0])}))
deltas=[]
for kind,cid in sorted(set((k[0],k[1]) for k in groups)):
 aa=sorted(groups[kind,cid,'direct'],key=lambda d:d['round']);bb=sorted(groups[kind,cid,'langchain'],key=lambda d:d['round'])
 deltas.append(dict(kind=kind,case_id=cid,wall_delta_ms=stats([b['client_wall_ms']-a['client_wall_ms'] for a,b in zip(aa,bb)]),wall_ratio=stats([b['client_wall_ms']/a['client_wall_ms'] for a,b in zip(aa,bb)])))
report={'status':'PASS','selection_rule':'repair-plan.json, all3 paired repetitions of affected warm cases and all cold slots; not selected by answer or speed','original_failures_retained':'latency-report.json; adoption-decision.initial.json; runs/cold-*','selected_slots':[d['slot'] for d in selected],'repair_wall_minus_monotonic_max_ms':max(abs(d['wall_clock_ms']-d['client_wall_ms']) for d in selected if d['slot'].startswith('repair-')),'quality_matches_manual_reviews':True,'contract_parity':'PASS','groups':summary,'paired':deltas}
(ev/'controlled-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
lines=['# P011 latency and resources','', 'All values below are milliseconds, original-root A vs candidate B with3 paired repetitions. Full distributions and component times are in controlled-comparison.json. No p95 or statistical significance claim.','', '| Phase | Case | A median | B median | Paired delta median (B−A) | Ratio median |','|---|---|---:|---:|---:|---:|']
for x in deltas:
 a=next(y for y in summary if y['kind']==x['kind'] and y['case_id']==x['case_id'] and y['implementation']=='direct');b=next(y for y in summary if y['kind']==x['kind'] and y['case_id']==x['case_id'] and y['implementation']=='langchain')
 lines.append(f"|{x['kind']}|{x['case_id']}|{a['metrics']['client_wall_ms']['median']:.1f}|{b['metrics']['client_wall_ms']['median']:.1f}|{x['wall_delta_ms']['median']:+.1f}|{x['wall_ratio']['median']:.3f}|")
lines += ['', 'Warm refers to an already exercised model-service workflow; each Python worker is new. Dense switches BGE/Qwen with MAX_LOADED_MODELS=1. Model load, embedding, search, context, HTTP generation and provider durations are reported separately, never summed as if disjoint. BM25 index-open is missing because the original boundary includes it in search; it is not filled with zero.', '', 'Initial138 slots and all4 cold HTTP500 errors remain in latency-report.json. OS sleep affected warm q14/q03/q06 and cold model loading. Preregistered repair-plan repeats both sides of every affected case/repetition and all18 cold slots under a process-scoped idle sleep assertion. Added epoch wall clocks agree with monotonic clocks within1second; OS caches were not cleared.', '', 'Offline verification overlapped portions of the original warm measurements; host load was not globally controlled. Small paired differences are descriptive, not proof of framework-caused speed changes. Resource reports exclude shared model-service memory from Python RSS.']
lines += ['', 'BM25 order/cache confounding: bm25-order-observations.json shows c01 first-in-pair prompt evaluation around3.2seconds versus about0.08seconds second, whichever implementation runs first. c03 shows about1.9seconds versus0.08seconds, and meal about0.78seconds versus0.08seconds. Three repetitions per case imply a2/1 first-position split even though the overall schedule is balanced. Thus the BM25 paired medians above are observed workflow differences, not an estimate of LangChain overhead. Dense also switches embedding/generation models; its observed90.7–486.0ms paired median differences do not isolate a causal framework cost.', '', 'Paired-delta median is computed from each B−A pair; it need not equal median(B)−median(A). Cold q03 illustrates this. Warm/cold, retriever and corpus are not pooled into a single speed percentage.']
(ev/'latency-resource-report.md').write_text('\n'.join(lines)+'\n')
print('controlled138 slots PASS; preserved initial4 errors')
