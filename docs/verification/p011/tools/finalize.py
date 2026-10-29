"""Write adoption only after complete, committed-protocol evidence gates exist."""
import json,hashlib,subprocess
from pathlib import Path
from datetime import datetime
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p011';s=root/'1. Naive RAG';b=s/'variants/langchain'
def read(name):return json.loads((ev/name).read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
for name in ['parity.json','live-parity.json','embedding-parity.json','controlled-comparison.json','preservation-check.json','index-final-check.json','copy-regression.json','browser-check.json']:
 assert read(name)['status']=='PASS',name
for name,count in [('baseline-tests-pass.log',107),('candidate-tests-pass.log',107),('langchain-tests-http.log',32),('root-tests.log',19),('harness-tests.log',12),('copy-tests.log',107),('copy-tests_langchain.log',32)]:
 t=(ev/name).read_text();assert f'Ran {count} tests' in t and t.rstrip().endswith('OK'),name
reviews=read('manual-reviews.json');assert len(reviews)==20 and not any(r['uncertain'] for r in reviews)
repaired_copy_log=(ev/'copy-tests_langchain-after-repair.log').read_text()
assert 'Ran 32 tests' in repaired_copy_log and repaired_copy_log.rstrip().endswith('OK')
quality=read('quality-review.json')['rows'];assert len(quality)==120
case_gates=[]
for cid in [r['case_id'] for r in reviews]:
 sides={impl:[r for r in quality if r['case_id']==cid and r['implementation']==impl] for impl in ['direct','langchain']};assert all(len(x)==3 for x in sides.values())
 sums={impl:{k:sum(r[k] for r in rows) for k in ['facts_met','facts_total','complete_answer','supported_claims','claims_total','appropriate_abstention','over_abstention','errors','contradictions','fabrications']} for impl,rows in sides.items()};a,c=sums['direct'],sums['langchain']
 positive=['facts_met','complete_answer','appropriate_abstention'];negative=['over_abstention','errors','contradictions','fabrications']
 assert all(c[k]>=a[k] for k in positive) and all(c[k]<=a[k] for k in negative)
 assert c['facts_total']==a['facts_total'];assert c['supported_claims']*max(a['claims_total'],1)>=a['supported_claims']*max(c['claims_total'],1)
 case_gates.append({'case_id':cid,'status':'PASS','metrics':sums})
ledger=[json.loads(l) for l in (ev/'ledger.jsonl').read_text().splitlines()];count=sum(x['dispatches'] for x in ledger);assert count<=320
source_commit=subprocess.check_output(['git','rev-parse','37acda8'],cwd=root,text=True).strip()
decision={'decision':'ADOPT_LANGCHAIN','scope':'No observed degradation in the fixed20-case experiment; not universal statistical equivalence or a fix for existing omissions','protocol_version':1,'protocol_sha256':sha(ev/'protocol.json'),'rubric_sha256':sha(ev/'rubric.json'),'protocol_commit':subprocess.check_output(['git','rev-parse','f008d32'],cwd=root,text=True).strip(),'adopted_plan':'63f9d259d76f322f1c6112b4306d0eb6941064a6','baseline_commit':'58e8eb793b95c524c256c0206e37aa15ff99c6ff','candidate_source_commit':source_commit,'candidate_manifest_sha256':sha(b/'copy-manifest.json'),'entry_sha256':sha(b/'scripts/rag_langchain.py'),'direct_entry_sha256':sha(s/'scripts/rag.py'),'gates':{k:'PASS' for k in ['preservation','contract','quality','stability_after_environment_repair','latency_and_resources','ui_cli_api','standalone_copy']},'case_quality_gates':case_gates,'initial_decision':'KEEP_DIRECT','initial_failure_evidence':'adoption-decision.initial.json','repair_plan_commit':subprocess.check_output(['git','rev-parse','8e58d03'],cwd=root,text=True).strip(),'selected_implementation':'langchain','source_path':'1. Naive RAG/variants/langchain','entry_path':'scripts/rag_langchain.py','ui_default':'direct; recommendation displayed separately','generation_dispatches':count,'max_dispatches':320,'followup_copy_excludes':['.venv','.runtime','__pycache__'],'evidence':['protocol.json','rubric.json','manual-reviews.json','quality-review.json','controlled-comparison.json','latency-report.json','resource-report.json','live-parity.json','embedding-parity.json','browser-check.json','copy-regression.json','index-final-check.json'],'remaining_p011_blockers':[],'followup_gate':'P010 must review this decision and adopt its own prepared contract; no automatic Hybrid or installable harness implementation','created_at':datetime.now().astimezone().isoformat()}
for path in [ev/'adoption-decision.json',b/'adoption-decision.json']:path.write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n')
print('ADOPT_LANGCHAIN',count,'actual dispatches')
