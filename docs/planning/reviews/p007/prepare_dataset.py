"""Freeze source-audited retrieval questions; no model/retrieval execution."""
import hashlib,json,subprocess,itertools,re
from pathlib import Path
REF='4cdee6f9583c899d76e95237af8b5de8d77d8012';BASE='2. Document Chunking/data/source-v4/'
def read(p):return subprocess.check_output(['git','show',f'{REF}:{p}'])
def obj(p):return json.loads(read(p))
items=obj(BASE+'policy-inventory.json')['items'];by_id={x['id']:x for x in items}
text=read(BASE+'extracted/canonical/hr-v4-handbook.txt').decode();digest=hashlib.sha256(text.encode()).hexdigest()
legacy=obj('1. Naive RAG/data/source-v2/evaluation-spec.json')
facts=[]
# One source fact may have multiple verified identical statements; accept ANY complete evidence set.
for old in legacy['facts']:
 choices=[]
 for req in old['required_spans']:
  hits=[x for x in items if x['authored_text']==req['quote']]
  assert hits,(old['fact_id'],req['quote'])
  choices.append(hits)
 evidence=[]
 for option in itertools.product(*choices):
  evidence.append([dict(x['canonical'],inventory_id=x['id']) for x in option])
 facts.append({'fact_id':old['fact_id'],'meaning':old['meaning'],'origin':'legacy_reaudited_v4','evidence_sets':evidence})
questions=[{'query_id':q['query_id'],'question':q['question'],'answerability':q['answerability'],'required_fact_ids':q['required_fact_ids'],'split':'tuning','origin':'observed_legacy'} for q in legacy['questions']]
assert len(questions)==14
new=[
('t01','tuning','생일 특별휴가 접수 시 어떤 정보를 연결하며 이미 등록된 생일·입사 정보를 다시 증명해야 하나요?',['BD-04-P01-S01','BD-04-P01-S02']),
('t02','tuning','생일휴가 시스템 장애로 접수 확인이 안 되면 어떤 임시 기록을 남기며 승인 면제가 되나요?',['BD-05-P01-S02','BD-05-P01-S03']),
('t03','tuning','연차 발생 일수 문의와 잔여 일수 문의는 어떤 기록을 각각 대조하나요?',['AN-02-P01-S01','AN-02-P01-S02']),
('t04','tuning','연차 신청을 기존 사용 기록과 연결할 때 확인할 정보와 중복된 요청의 처리 방법은 무엇인가요?',['AN-05-P01-S01','AN-05-P01-S03']),
('t05','tuning','재택근무 신청 날짜가 여러 주에 걸치거나 대상 주와 맞지 않으면 담당자는 어떻게 처리하나요?',['RM-04-P01-S01','RM-04-P01-S02']),
('t06','tuning','이사한 집에서 재택하려면 언제 누구에게 요청하며 주소 변경 기록에는 무엇을 남기나요?',['RM-05-P01-S01','RM-05-P01-S02','RM-05-P02-S01']),
('t07','tuning','복지 내역을 확인할 때 어떤 항목을 대조하며 생일 포인트와 식대를 하나의 합계로 더해도 되나요?',['WF-04-P01-S01','WF-04-P01-S03']),
('t08','tuning','식대 문의에서 화면마다 근무 형태가 다르면 어떤 순서로 확인하고 어떤 근거 선택을 피해야 하나요?',['WF-05-P01-S01','WF-05-P01-S02','WF-05-P01-S03']),
('t09','tuning','교육휴가 신청에서 시험 일정과 선택 날짜가 다르거나 여러 시험을 함께 적으면 어떻게 확인하나요?',['ED-03-P01-S02','ED-03-P01-S03']),
('t10','tuning','교육휴가 신청의 직무 관련 설명이 부족하면 담당자가 시험 합격 가능성을 평가하거나 미충족으로 기록해도 되나요?',['ED-04-P01-S02','ED-04-P01-S03']),
('t11','tuning','출장 신청서의 출발일·방문지가 서로 다르면 즉시 취소해야 하나요? 어떤 기록을 남기나요?',['TR-04-P01-S02','TR-04-P01-S03']),
('t12','tuning','새 출장 일정표가 오면 모든 항목을 변경 요청으로 처리하나요? 오입력 정정과 실제 변경은 어떻게 구분하나요?',['TR-05-P01-S01','TR-05-P01-S02','TR-05-P01-S03']),
('h01','holdout','생일휴가 날짜를 바꿀지 문의만 했는데 새 신청으로 등록해도 되나요? 실제 변경 요청에서는 무엇을 기록하나요?',['BD-06-P01-S01','BD-06-P01-S03']),
('h02','holdout','연차 날짜 변경과 오전·오후 반차 변경은 어떻게 구분하며 의사 확인 전 차감량을 바꿔도 되나요?',['AN-09-P01-S01','AN-09-P01-S02','AN-09-P01-S03']),
('h03','holdout','연차 신청 중 일부 날짜와 교육휴가 응시 계획을 취소하려는데, 각각 어떤 범위를 확인하고 기록해야 하나요?',['AN-10-P01-S01','AN-10-P01-S02','ED-06-P01-S01','ED-06-P01-S02','ED-06-P01-S03']),
('h04','holdout','재택 중 VPN 문제가 생기면 어떤 유형으로 나눠 기록하고 일반 확인으로 해결하지 못하면 어떻게 하나요?',['RM-07-P01-S01','RM-07-P01-S03']),
('h05','holdout','재택 승인 결과는 있는데 알림이 오지 않았다면 무엇을 확인하고, 알림 장애로 발송 이력이 없을 때는 어떻게 안내하나요?',['RM-09-P01-S01','RM-09-P01-S02','RM-09-P01-S03']),
('h06','holdout','복지 조회 화면이 열리지 않으면 기억하는 금액을 확정값으로 저장하거나 미지급으로 처리해도 되나요?',['WF-07-P01-S01','WF-07-P01-S02','WF-07-P01-S03']),
('h07','holdout','복지 담당자의 설명과 표시 내역이 다르면 어떤 항목을 대조하며, 예상 금액과 다르다는 이유로 지급 기준을 바꾸나요?',['WF-08-P01-S01','WF-08-P01-S02','WF-08-P01-S03']),
('h08','holdout','교육휴가 뒤 시험 후기를 제출하면 합격 여부가 자격 조건이 되거나 다음 시험 휴가가 자동 신청되나요?',['ED-08-P01-S01','ED-08-P01-S02','ED-08-P01-S03']),
('h09','holdout','출장 신청 시스템 장애 시 어떤 임시 정보를 남기고, 이것으로 승인 기한이나 팀장 승인을 생략할 수 있나요?',['TR-07-P01-S01','TR-07-P01-S02','TR-07-P01-S03']),
('h10','holdout','출장 비용 자료의 이용 날짜가 일정표와 다르면 잘못된 비용인가요? 먼저 확인할 정보는 무엇인가요?',['TR-09-P01-S01','TR-09-P01-S02','TR-09-P01-S03'])]
for qid,split,q,ids in new:
 f='new-'+qid;rows=[by_id[i] for i in ids]
 facts.append({'fact_id':f,'meaning':q,'origin':'added_procedure_source_audit','evidence_sets':[[dict(x['canonical'],inventory_id=x['id']) for x in rows]]})
 questions.append({'query_id':qid,'question':q,'answerability':'answerable','required_fact_ids':[f],'split':split,'origin':'new_source_v4','article_ids':sorted({x['article_id'] for x in rows})})
for qid,q,reason in [('h11','재택근무 중 전기요금은 월 얼마까지 지원하나요?','기기/VPN·근무 절차는 있으나 전기요금 지원 금액 규정 없음.'),('h12','개인 차량으로 출장할 때 유류비의 킬로미터당 지급 단가는 얼마인가요?','출장 비용 자료의 연결/보완 절차는 있으나 거리당 유류비 지급 단가 없음.')]:
 questions.append({'query_id':qid,'question':q,'answerability':'unanswerable','required_fact_ids':[],'split':'holdout','origin':'new_source_v4','source_audit_reason':reason})
for f in facts:
 for evidence in f['evidence_sets']:
  assert evidence
  for s in evidence:assert text[s['start']:s['end']]==s['quote'] and s['canonical_sha256']==digest
byf={f['fact_id']:f for f in facts}
for q in questions:assert all(f in byf for f in q['required_fact_ids'])
# Split new questions by article group, with legacy statements explicitly exposed in tuning.
tune={a for q in questions if q['split']=='tuning' for a in q.get('article_ids',[])}
hold={a for q in questions if q['split']=='holdout' for a in q.get('article_ids',[])}
assert not tune&hold
out={'schema_version':2,'status':'SOURCE_AUDITED_RETRIEVAL_SET','p016_completion_commit':REF,'canonical_sha256':digest,'reviewer_kind':'Codex_source_audit_not_human_approval','evidence_semantics':'AND required facts; OR evidence_sets per fact; AND spans within each evidence set','freeze_policy':'No retrieval used to choose questions; holdout excluded from tuning/default UI until configs frozen. After first holdout reveal treat as observed. Same author/source, not independent human evaluation.','scope_note':'Source-span coverage of enumerated evidence, not exhaustive semantic relevance; paraphrased equivalent passages may remain unannotated.','facts':facts,'questions':questions,'review':{'legacy_reaudited':14,'new_tuning':12,'holdout_answerable':10,'holdout_unanswerable':2,'new_tuning_holdout_article_overlap':[],'negative_audit':'Original/full authored handbook reviewed via policy inventory and article map; absence is document-bounded, not denial of a real benefit.'}}
p=Path('docs/planning/specs/P007-retrieval-dataset.json');p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('dataset:',len(facts),'facts',len(questions),'questions; tuning26/holdout12; exact spans verified; alternatives:',[(f['fact_id'],len(f['evidence_sets'])) for f in facts if len(f['evidence_sets'])>1])
