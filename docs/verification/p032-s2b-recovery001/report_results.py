"""Model-free replay plus independent Unicode-position and RRF arithmetic."""
from pathlib import Path
import json,importlib.util,math,struct,collections,html,statistics,os
E=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('rt',E/'runtime.py');rt=importlib.util.module_from_spec(s);s.loader.exec_module(rt)
R=rt.RUN
from rag_package import chunk_artifact,chunk_compare,embedding,reranker,llm,rag,retrieval
from rag_package.storage import verify

def deny(*a,**k):raise AssertionError('report model calls forbidden')
embedding.encode=reranker.score=llm.invoke=rag.ask=rag.compare=retrieval.build=deny

def coverage(chunks,facts):
 positions=collections.defaultdict(set)
 for c in chunks:positions[c['document_id']].update(range(c['start'],c['end']))
 hit=[f['fact_id'] for f in facts if any(all(set(range(s['start'],s['end']))<=positions[s['document_id']] for s in alt['spans']) for alt in f['alternatives'])]
 return {'fulfilled_ids':hit,'fulfilled':len(hit),'total':len(facts),'fact_recall':len(hit)/len(facts) if facts else None,'all_required':len(hit)==len(facts) if facts else None,'reason':None if facts else 'no_required_facts'}

def run():
 m=rt.read(R/'manifest.json');rt.check_frozen(m);rt.check_recovery();before=rt.sha(R/'ledger.json');ledger=rt.read(R/'ledger.json')
 assert ledger['status'] in ('complete','halted')
 qs=rt.read(R/'input/questions.json');facts={q['question_id']:q['required_facts'] for q in rt.read(R/'input/facts.json')['questions']};methods=('fixed','recursive','structure','semantic')
 summary=chunk_compare.load(R/'comparison') if (R/'comparison/manifest.json').exists() else None
 rows=[];boundaries={};comparisons=0
 for method in methods:
  path=R/'semantic' if method=='semantic' else R/'input/chunks'/method
  if (path/'manifest.json').exists():
   cr,docs,chunks,_=chunk_artifact.load(path);chunk_artifact.replay(path)
   for c in chunks:assert c['text']==next(d['text'] for d in docs if d['document_id']==c['document_id'])[c['start']:c['end']]
   lengths=[len(c['text']) for c in chunks]
   boundaries[method]={'count':len(chunks),'median_chars':statistics.median(lengths),'min_chars':min(lengths),'max_chars':max(lengths),'statistics':cr['statistics'],'work':cr['work'],'fingerprint':cr['chunk_fingerprint']}
   if method=='semantic':
    us=rt.read(path/'units.json');raw=(path/'unit-vectors.f32').read_bytes();dim=cr['details']['dimension'];vectors=[v for v in struct.iter_unpack('<'+str(dim)+'f',raw)]
    assert len(vectors)==len(us)==567
    distances=cr['details']['distances'];base=cr['base'];start=us[0]['start'];expected=[];reason_counts=collections.Counter()
    for i in range(1,len(us)):
     previous,current=us[i-1],us[i];assert previous['document_id']==current['document_id']
     a,b=vectors[i-1],vectors[i];cos=math.fsum(x*y for x,y in zip(a,b))/math.sqrt(math.fsum(x*x for x in a)*math.fsum(x*x for x in b));dist=1-max(-1,min(1,cos))
     reason='maximum' if current['end']-start>192 else 'semantic' if current['start']-start>=120 and dist>=.35 else None
     d=distances[i-1];assert abs(d['distance']-dist)<1e-12 and d['reason']==reason and d['boundary']==bool(reason)
     if reason:expected.append((start,current['start'],reason));reason_counts[reason]+=1;start=current['start']
    expected.append((start,us[-1]['end'],'document_end'))
    assert [(b['start'],b['end'],b['reason']) for b in base]==expected
    assert [(c['start'],c['end']) for c in chunks]==[(a if i==0 else max(expected[i-1][0],a-64),end) for i,(a,end,reason) in enumerate(expected)]
    boundaries[method]['independent_distance_checks']=len(distances);boundaries[method]['cut_reasons']=dict(reason_counts)
    boundaries[method]['maximum_cut_fraction']=reason_counts['maximum']/sum(reason_counts.values()) if reason_counts else None
  build=R/'checkpoints'/method/'build'
  if (build/'manifest.json').exists():bm,ds,cs=retrieval.load_build(build,retrieval.config(R/'input/configs'/(method+'.json'))[0]);byid={c['chunk_id']:c for c in cs}
  for q in qs:
   p=R/'checkpoints'/method/q['id'];row={'method':method,'question_id':q['id'],'question':q['question'],'status':'not_executed','metrics':None}
   if (p/'manifest.json').exists():
    verify(p,'answer');r=rt.read(p/'result.json');assert r['status']=='preview' and r['generation_requests']==0 and r['answer'] is None and r['error'] is None
    totals=collections.defaultdict(float)
    for branch in ('bm25','dense'):
     for rank,c in enumerate(r['retrieval_trace'][branch],1):assert c['rank']==rank;totals[c['chunk_id']]+=1/(60+rank)
    full=sorted(totals,key=lambda cid:(-totals[cid],cid));assert full[:5]==[c['chunk_id'] for c in r['candidates']]
    for c in r['candidates']:assert abs(totals[c['chunk_id']]-c['score'])<1e-15
    levels={'branch_union':[byid[c] for c in full],'candidate_N20':[byid[c] for c in full[:20]],'top_k':[byid[c['chunk_id']] for c in r['candidates']],'contexts':r['contexts']}
    metrics={k:coverage(v,facts[q['id']]) for k,v in levels.items()}
    for name,key in [('branch_union','candidate'),('top_k','top_k'),('contexts','contexts')]:assert metrics[name]==r['metrics']['facts'][key];comparisons+=1
    used=0;contexts=[];excluded=[]
    for item in r['candidates']:
     c=byid[item['chunk_id']]
     if used+len(c['text'])<=2000:contexts.append(c);used+=len(c['text'])
     else:excluded.append(item['chunk_id'])
    assert contexts==r['contexts'] and excluded==[c['chunk_id'] for c in r['excluded']]
    row.update(status='complete',metrics=metrics,branch_union_count=len(full),candidate_N20_count=min(20,len(full)),context_chars=used,latency_ms=r['latency_ms'],chunk_metrics={'Recall':None,'MRR':None,'nDCG':None,'reason':'no_new_chunk_qrels'},answer_quality=None,
     selected=[{'rank':n+1,'chunk_id':c['chunk_id'],'start':c['start'],'end':c['end'],'text':c['text'],'heading_path':c.get('heading_path'),'document_id':c['document_id'],'pages':c.get('pages')} for n,c in enumerate(contexts)],
     branch_union_ids=full,candidate_N20_ids=full[:20],excluded=excluded)
   rows.append(row)
 aggregates={}
 for method in methods:
  group=[r for r in rows if r['method']==method];valid=[r for r in group if r['metrics'] and r['metrics']['contexts']['total']]
  aggregates[method]={'complete':sum(r['status']=='complete' for r in group),'not_executed':sum(r['status']=='not_executed' for r in group),'valid_questions':len(valid),'levels':{}}
  for level in ('branch_union','candidate_N20','top_k','contexts'):
   hit=sum(r['metrics'][level]['fulfilled'] for r in valid);total=sum(r['metrics'][level]['total'] for r in valid)
   aggregates[method]['levels'][level]={'fulfilled':hit,'total':total,'micro':hit/total if total else None,'macro':sum(r['metrics'][level]['fact_recall'] for r in valid)/len(valid) if valid else None,'all_required_questions':sum(r['metrics'][level]['all_required'] for r in valid)}
 assert rt.sha(R/'ledger.json')==before
 preserv=rt.read(E/'preservation.json');old=Path(preserv['old_environment']);actual={str(p.relative_to(old)):rt.sha(p) for p in sorted(old.rglob('*')) if p.is_file() and not p.is_symlink()};assert actual==preserv['old_environment_files']
 observations=[o.get('observation',{}) for o in ledger['operations']];assert all(o.get('worker_exited') and o.get('resume_safe') for o in observations if o.get('workers_started'))
 out={'execution_status':ledger['status'],'P032_complete':False,'aggregates':aggregates,'rows':rows,'boundaries':boundaries,'independent_fact_comparisons':comparisons,'replay_model_calls':0,'parent_workers':1,'child_workers':ledger['reserved_workers'],'cumulative_workers':1+ledger['reserved_workers'],'child_requested_items':ledger['reserved_items'],'cumulative_requested_items':567+ledger['reserved_items'],'known_completed_items':sum(o['completed_items'] or 0 for o in ledger['operations']),'unknown_completed_jobs':1+sum(o['completed_items'] is None for o in ledger['operations']),'parent_unknown_requested_items':567,'original_start':ledger['started_at'],'original_deadline':ledger['deadline'],'sampled_peak_rss_bytes':max((o.get('sampled_peak_rss_bytes') or 0 for o in observations),default=0),'parent_files_preserved':len(preserv['parent_files']),'old_environment_files_preserved':len(actual),'S1_files_preserved':len(m['files']['S1']),'S2a_files_preserved':len(m['files']['S2a']),'protected_files_preserved':len(m['files']['protected']),'ledger_hash':before,'forbidden_calls':{'LLM':0,'API':0,'Drive':0,'reranker':0,'evaluator':0,'Ollama':0,'keys':0,'model_download':0}}
 out['stage_work']=[{'label':o['label'],'requested_items':o['requested_items'],'completed_items':o['completed_items'],'status':o['status'],'elapsed_ms':o.get('observation',{}).get('elapsed_ms'),'sampled_peak_rss_bytes':o.get('observation',{}).get('sampled_peak_rss_bytes')} for o in ledger['operations']]
 out['latency_note']='Each operation starts a new owned worker; startup/model loading included; OS caches may remain warm. This is not isolated hardware performance benchmarking.'
 out['cost_measured']=False
 rt.write(E/'results.json',out)
 rt.write(E/'final-checks.json',{'status':'PASS','execution_status':ledger['status'],'complete_rows':sum(r['status']=='complete' for r in rows),'independent_fact_comparisons':comparisons,'worker_reaped':True,'model_calls_this_audit':0,'P032_complete':False,'ledger_unchanged':True,'parent_files':len(preserv['parent_files']),'old_env_files':len(actual),'S1':len(m['files']['S1']),'S2a':len(m['files']['S2a']),'protected':len(m['files']['protected'])})
 print(json.dumps({'status':'PASS','execution':ledger['status'],'aggregates':aggregates,'semantic':{k:v for k,v in boundaries.get('semantic',{}).items() if k in ('count','cut_reasons','maximum_cut_fraction')},'workers':out['cumulative_workers'],'items':out['cumulative_requested_items']}))
if __name__=='__main__':run()
