"""Explicit pre-ranking review decisions after reading the entire 23-page corpus."""
from pathlib import Path
from rag_package.storage import read_json,write_json,fingerprint,digest
from rag_package import fact_metrics,documents,search_metrics
P=Path(__file__).resolve().parent/'input';q=read_json(P/'qrels-provisional.json');rows=read_json(P/'qrels-audit-provisional.json');cs=read_json(P/'build-bm25/chunks.json')
# Tiny sentence tails alone neither state a requested fact nor approved supplement.
zero={('gt03',85):'Only ending 제시하지 않는다 remains; neither VPN nor public-computer condition is stated.',('gt08',149):'Only ending of already-truncated supplementary sentence; following text is cancellation withdrawal, not requested cancellation scope.',('gt06',171):'Only 그 항목들의 결과로 전파하지 않는다 remains without subject; following notification steps do not answer requested exception.'}
for r in rows:
 key=(r['question_id'],r['chunk_index'])
 if key in zero:r.update(grade=0,reasons=[],review_note=zero[key]);q['judgments'][r['question_id']][r['chunk_id']]=0
 r['reviewed']=True
 if not r['grade'] and 'review_note' not in r:r['review_note']='Entire corpus and this source interval checked against the question: no sufficient/partial required fact or approved supplement; lexical overlap alone is not relevance.'
q['judgments_complete']=True
assert len(rows)==len(cs)*10 and all(len(q['judgments'][f'gt{i:02}'])==len(cs) for i in range(1,11))
assert not any(q['judgments']['gt09'].values()) and not any(q['judgments']['gt10'].values())
write_json(P/'qrels.json',q);write_json(P/'qrels-audit.json',rows)
review=read_json(P/'source-review.json');review.update(status='frozen_before_ranking',chunk_review='entire canonical corpus read; every fixed chunk mapped; nonzero boundaries reread; three semantically empty tails explicitly excluded',author='Codex dev',reviewer='Codex dev same-agent source review; human GT approval separate',zero_overrides=[{'question_id':qid,'chunk_index':i,'reason':why} for (qid,i),why in zero.items()],all_chunk_judgments_reviewed=True,judgments_complete=True,limitations=['One synthetic public training corpus, 10 exposed questions, no independent blind annotation','Conservative exact span coverage is not semantic LLM correctness','PDF running headers/footers remain in canonical source and may affect retrieval'],files={n:digest((P/n).read_bytes()) for n in ('facts.json','qrels.json','qrels-audit.json','questions.json','claims-mapping.json')})
write_json(P/'source-review-final.json',review)
# Complete immutable input identity includes source, chunk map, questions, labels and model plans later.
write_json(P/'frozen-inputs.json',{'status':'frozen_before_rankings','source_fingerprint':q['source_fingerprint'],'chunk_fingerprint':q['chunk_fingerprint'],'questions_hash':q['questions_hash'],'files':{n:digest((P/n).read_bytes()) for n in ('facts.json','qrels.json','qrels-audit.json','questions.json','claims-mapping.json','source-review-final.json')},'generation_calls':0,'retrieval_rankings_observed':0})
print({'chunks':len(cs),'judgments':len(rows),'nonzero':sum(r['grade']>0 for r in rows),'required':38,'status':review['status']})
