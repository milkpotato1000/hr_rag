"""Model-free final audit of the inherited run and frozen result matrix."""
from pathlib import Path
import json,hashlib,time,sys
E=Path(__file__).resolve().parent;C=E/'continuation001';R=C/'run';load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=load(R/'manifest.json');parent=load(E/'run001/ledger.json');child=load(R/'ledger.json')
assert all(sha(E/'run001'/n)==h for n,h in m['parent_identity'].items())
assert child['jobs'][:len(parent['jobs'])]==parent['jobs']
assert child['started_at']==parent['started_at']==1795801676.159772
assert m['deadline']==1795808876.159772 and child['active'] is None
reserved=[j for j in child['jobs'] if j.get('reserved')];started=[j for j in child['jobs'] if j.get('workers_started')]
assert len(reserved)==sum(child['reservations'].values())<=73
assert sum(j['requested_pairs'] for j in reserved if j['category']=='reranker_smoke')==child['reranker_smoke_pairs']<=100
assert sum(j['requested_pairs'] for j in reserved if j['category']=='reranker_full')==child['reranker_full_pairs']<=400
assert all(j['observation']['worker_exited'] and j['observation']['resume_safe'] for j in started)
assert all(s['rss_bytes']<4*1024**3 and s['os']['pressure']=='normal' for j in started for s in j['observation']['samples'])
assert all(j['finished_at']<m['deadline'] for j in child['jobs'][len(parent['jobs']):])
assert not any(j['label'].startswith('e5') for j in child['jobs'][len(parent['jobs']):])
p=load(E/'preservation.json');assert all(sha(E.parents[2]/n)==h for n,h in p['files'].items())
preparations=[j['preparation'] for j in child['jobs'] if j.get('preparation')]
for result in preparations:
 assert result['status']=='ready'
 for work in result['work'].values():
  if isinstance(work,dict) and work.get('workers_started'):assert work['worker_exited'] is True
summary=load(C/sys.argv[1]/'summary.json');counts={} 
facts={q['question_id']:q['required_facts'] for q in load(E/'input/facts.json')['questions']}
coverage_checked=0
for row in summary['rows']:
 if row['status']!='complete':continue
 covered={}
 for chunk in row['contexts']:covered.setdefault(chunk['document_id'],set()).update(range(chunk['start'],chunk['end']))
 expected=[]
 for fact in facts[row['question_id']]:
  if any(all(set(range(span['start'],span['end'])).issubset(covered.get(span['document_id'],set())) for span in alternative['spans']) for alternative in fact['alternatives']):expected.append(fact['fact_id'])
 actual=row['metrics']['facts']['contexts'];assert set(actual['fulfilled_ids'])==set(expected) and actual['fulfilled']==len(expected)
 if not facts[row['question_id']]:assert actual['fact_recall'] is None
 coverage_checked+=1
for kind in ('search','rerank'):
 for status in ('complete','failed','not_executed'):counts[kind+'_'+status]=sum(r['kind']==kind and r['status']==status for r in summary['rows'])
r={'status':'PASS','S1_matrix_complete':counts['search_complete']==50 and counts['rerank_complete']==30,'P032_complete':False,'parent_files_verified':len(m['parent_identity']),'parent_failed_job_preserved':True,'parent_job_prefix_identical':True,'started_at':child['started_at'],'deadline':m['deadline'],'inference_reservations':len(reserved),'inference_started':len(started),'inference_completed':sum(j['status']=='complete' for j in started),'inference_failed':sum(j['status']=='failed' for j in started),'reranker_reserved_pairs':child['reranker_smoke_pairs']+child['reranker_full_pairs'],'reranker_known_completed_pairs':sum(j['completed_pairs'] for j in started if j['category'].startswith('reranker') and j.get('completed_pairs') is not None),'reranker_completed_pairs_unknown_jobs':sum(j.get('completed_pairs') is None for j in started if j['category'].startswith('reranker')),'reranker_unknown_requested_pairs':sum(j['requested_pairs'] for j in started if j['category'].startswith('reranker') and j.get('completed_pairs') is None),'download_attempts':child['download_attempts'],'preparation_workers':sum(w.get('workers_started',0) for result in preparations for w in result['work'].values() if isinstance(w,dict)),'all_workers_exited':True,'sampled_RSS_and_pressure_within_limits':True,'preserved_files':len(p['files']),**counts,'independent_unicode_context_coverage_rows':coverage_checked,'model_calls_this_audit':0,'generation_Drive_evaluator_Ollama_calls':0,'holds':'P013/P014/P029 C4 unchanged'}
(C/'final-checks.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False))
