"""Aggregate only manually reviewed exact outputs. Never infer semantic PASS."""
import json,hashlib,statistics,collections,sys
from pathlib import Path
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p011';proto=json.loads((ev/'protocol.json').read_text());reviews={r['case_id']:r for r in json.loads((ev/'manual-reviews.json').read_text())};paths=sorted((ev/'runs').glob('warm-*.json'))
if len(paths)!=120:raise ValueError(f'expected120 completed warm slots, got{len(paths)}')
quality=[];pairs=collections.defaultdict(dict)
for path in paths:
 d=json.loads(path.read_text());r=d['result'];review=reviews[d['case_id']];value={k:r[k] for k in ('status','answer','citations','reason')};sig=hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 if sig!=review['reviewed_output_sha256']:raise ValueError('New output requires manual source review: '+path.name)
 facts=review['facts'];claims=review['claims'];met=sum(f['met'] for f in facts);supported=sum(c['selected_citations_support'] for c in claims)
 quality.append(dict(slot=d['slot'],case_id=d['case_id'],implementation=d['implementation'],facts_met=met,facts_total=len(facts),complete_answer=review['complete_required_facts'],supported_claims=supported,claims_total=len(claims),citation_support_rate=supported/len(claims) if claims else None,appropriate_abstention=review['appropriate_abstention'],over_abstention=review['over_abstention'],errors=review['errors'],contradictions=review['contradictions'],fabrications=review['fabrications'],uncertain=review['uncertain'],reviewed_output_sha256=sig,context_sufficient=review['context_sufficient']))
 pairs[d['case_id'],d['round']][d['implementation']]=d
parity=[]
for (cid,round),pair in pairs.items():
 a,b=[pair[k] for k in ('direct','langchain')];ta,tb=a['result']['trace'],b['result']['trace']
 keys=['candidates','contexts','excluded','context_chars','prompt','generation_calls','citation_assembly','validation','citation_structure_valid','corpus_sha256','settings']
 diffs=[k for k in keys if ta.get(k)!=tb.get(k)]
 for k in ['request','allowed_ids','schema_sha256','request_dispatched','model','digest']:
  if ta.get('generation',{}).get(k)!=tb.get('generation',{}).get(k):diffs.append('generation.'+k)
 wa=[x['data'] for x in a['wire'] if x['url'].endswith('/api/chat')];wb=[x['data'] for x in b['wire'] if x['url'].endswith('/api/chat')]
 if wa!=wb:diffs.append('serialized_http_chat_payload')
 ea=[(x['body'],x.get('embeddings_sha256')) for x in a['http'] if x['route']=='/api/embed'];eb=[(x['body'],x.get('embeddings_sha256')) for x in b['http'] if x['route']=='/api/embed']
 if ea!=eb:diffs.append('live_embedding_input_output')
 for side in (a,b):
  trace=side['result']['trace'];n=sum(x['url'].endswith('/api/chat') for x in side['wire']);assert n==trace['generation_calls'] and n<=1
  ctx={c['chunk_id']:c for c in trace['contexts']}
  for c in side['result']['citations']:assert c['quote'].encode()==ctx[c['chunk_id']]['text'].encode()
  for w in side['wire']:
   if w['url'].endswith('/api/chat'):
    payload=json.loads(w['data']);assert payload['messages']==trace['prompt']['messages'];assert {k:payload[k] for k in trace['generation']['request']}==trace['generation']['request']
 parity.append(dict(case_id=cid,round=round,differences=diffs))
(ev/'quality-review.json').write_text(json.dumps({'rows':quality,'source':'manual-reviews.json','exact_reviewed_outputs':True},ensure_ascii=False,indent=2)+'\n')
(ev/'live-parity.json').write_text(json.dumps({'status':'PASS' if all(not p['differences'] for p in parity) else 'FAIL','pairs':parity,'quote_bytes':'PASS','dispatch_counts':'PASS'},indent=2)+'\n')
# Summarize paired latency without combining overlapping timing intervals.
allruns=[json.loads(p.read_text()) for p in sorted((ev/'runs').glob('*.json')) if p.name.startswith(('warm-','cold-'))]
if sum(d['kind']=='cold' for d in allruns)!=18:raise ValueError('expected18 cold slots')
def stats(values):
 v=[x for x in values if x is not None]
 return {'n':len(v),'missing':len(values)-len(v),'median':statistics.median(v) if v else None,'min':min(v) if v else None,'max':max(v) if v else None,'values':v}
def metrics(d):
 t=d['result']['trace'];r=t.get('retrieval',{});g=t.get('generation',{}).get('observations',{});times=t['timings_ms']
 return {'client_wall_ms':d['client_wall_ms'],'worker_total_ms':d['worker_total_ms'],'import_ms':d['import_ms'],'pipeline_total_ms':times['total'],'index_open_ms':r.get('index_open_ms'),'embedding_ms':r.get('embedding_ms'),'search_ms':r.get('search_ms'),'context_ms':times['context'],'generation_ms':times['generation'],'generation_http_ms':sum(h['wall_ms'] for h in d['http'] if h['route']=='/api/chat'),'provider_load_ms':g.get('load_duration',0)/1e6 if 'load_duration' in g else None,'provider_prompt_ms':g.get('prompt_eval_duration',0)/1e6 if 'prompt_eval_duration' in g else None,'provider_eval_ms':g.get('eval_duration',0)/1e6 if 'eval_duration' in g else None,'provider_total_ms':g.get('total_duration',0)/1e6 if 'total_duration' in g else None,'peak_rss_bytes':d['peak_rss_bytes']}
groups=collections.defaultdict(list)
for d in allruns:groups[d['kind'],d['case_id'],d['implementation']].append(d)
summary=[]
for (kind,cid,impl),ds in groups.items():summary.append(dict(kind=kind,case_id=cid,implementation=impl,status_counts=dict(collections.Counter(d['result']['status'] for d in ds)),metrics={k:stats([metrics(d)[k] for d in ds]) for k in metrics(ds[0])}))
deltas=[]
for kind,cid in sorted(set((k[0],k[1]) for k in groups)):
 aa=sorted(groups[kind,cid,'direct'],key=lambda d:d['round']);bb=sorted(groups[kind,cid,'langchain'],key=lambda d:d['round'])
 deltas.append(dict(kind=kind,case_id=cid,wall_delta_ms=stats([b['client_wall_ms']-a['client_wall_ms'] for a,b in zip(aa,bb)]),wall_ratio=stats([b['client_wall_ms']/a['client_wall_ms'] for a,b in zip(aa,bb)])))
(ev/'latency-report.json').write_text(json.dumps({'unit':'ms except peak_rss_bytes; macOS getrusage','overlapping_intervals_not_added':True,'processes':'fresh Python process per slot; warm means workflow/model-service sequence, not warm imports','model_cache':'MAX_LOADED_MODELS=1; Dense alternates BGE/Qwen; inspect load durations','os_cache_cleared':False,'sample_size':'3 repeats per case, no p95/significance assertion','groups':summary,'paired':deltas},indent=2)+'\n')
print('reviewed120 slots; live parity',all(not p['differences'] for p in parity),'latency138 slots')
