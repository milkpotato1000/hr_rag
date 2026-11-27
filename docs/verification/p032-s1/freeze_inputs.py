"""P032 S1: regenerate reviewed source mapping before any retrieval ranking.
Never uses old offsets, lexical query similarity, model output or search scores.
"""
from pathlib import Path
import re,json,shutil
from rag_package import documents,chunks,retrieval,fact_metrics
from rag_package.storage import read_json,write_json,fingerprint,digest
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent/'input'
packet=read_json(ROOT/'evaluation/project_b/preparation/artifacts/run004/packet.json')
audit=read_json(ROOT/'docs/planning/reviews/p032-source-fact-audit.json')
sm,docs=documents.load_snapshot(OUT/'snapshot-installed');text=docs[0]['text']
assert documents.load_snapshot(OUT/'snapshot')[0]['fingerprint']==sm['fingerprint']
# Text matching ignores PDF line breaks for locating only; stored quotes remain exact.
positions=[i for i,c in enumerate(text) if not c.isspace()];normalized=''.join(text[i] for i in positions)
def span(quote):
 needle=''.join(quote.split());assert normalized.count(needle)==1,(quote,normalized.count(needle))
 i=normalized.index(needle);a,b=positions[i],positions[i+len(needle)-1]+1
 return {'document_id':'hr-handbook','start':a,'end':b,'quote':text[a:b]}
# Expand fragment citations to retain the policy subject and conditions.
fix={
'gt01-c08':'생일 특별휴가는 생일이 속한 달의 근무일에 사용한다. 해당 월을 넘겨 이월하거나 현금으로 지급하지 않는다.',
'gt03-c01':'입사 후 1개월이 지난 직원은 보안 교육을 이수하면 재택근무를 신청할 수 있다. 현장 장비 운영 직무는 재택 대상에서 제외한다.',
'gt03-c02':'입사 후 1개월이 지난 직원은 보안 교육을 이수하면 재택근무를 신청할 수 있다. 현장 장비 운영 직무는 재택 대상에서 제외한다.',
'gt03-c04':'재택근무는 매주 최대 2일이며 전주 금요일까지 팀장 승인을 받는다.',
'gt03-c08':'재택근무 시 회사 지급 기기와 회사 VPN을 사용한다. 공용 컴퓨터로 내부 문서에 접근할 수 없다.',
'gt04-c04':'재직자에게 생일 축하 포인트 3만 점을 지급한다. 이 포인트는 휴가 신청 자격이나 승인 여부와 별개다.',
'gt04-c05':'재직자에게 생일 축하 포인트 3만 점을 지급한다. 이 포인트는 휴가 신청 자격이나 승인 여부와 별개다.',
'gt05-c03':'생일 특별휴가 및 연차와 별도로 관리한다. 교육휴가 내역을 연차 차감 기록이나 생일 특별휴가 기록으로 자동 전환하지 않는다.',
'gt05-c04':'생일 특별휴가 및 연차와 별도로 관리한다. 교육휴가 내역을 연차 차감 기록이나 생일 특별휴가 기록으로 자동 전환하지 않는다.',
'gt06-c02':'이때 담당자는 전달받은 출장 목적, 출발 예정일, 전달 시점과 접수 확인이 필요한 사유를 임시 기록한다. 임시 기록은 신청 내용을 보존하기 위한 것이며 TR-01@v4의 승인 기한이나 팀장 승인 조건을 없애는 예외로 안내하지 않는다.',
'gt06-c03':'이때 담당자는 전달받은 출장 목적, 출발 예정일, 전달 시점과 접수 확인이 필요한 사유를 임시 기록한다. 임시 기록은 신청 내용을 보존하기 위한 것이며 TR-01@v4의 승인 기한이나 팀장 승인 조건을 없애는 예외로 안내하지 않는다.',
'gt06-c04':'이때 담당자는 전달받은 출장 목적, 출발 예정일, 전달 시점과 접수 확인이 필요한 사유를 임시 기록한다. 임시 기록은 신청 내용을 보존하기 위한 것이며 TR-01@v4의 승인 기한이나 팀장 승인 조건을 없애는 예외로 안내하지 않는다.',
'gt06-c06':'출장 승인으로 휴가나 재택근무가 자동 승인되지는 않는다.',
'gt07-c02':'임시 기록은 새로운 휴가 자격이나 승인 면제가 아니며, 원래 신청 시점과 이후 복구 입력 시점을 구별하기 위한 자료로 사용한다.',
'gt07-c05':'시스템이 복구되면 기존 기록이 실제로 생성되어 있는지를 먼저 찾아보고,',
'gt07-c06':'존재하지 않는 경우에만 임시 기록과 연결하여 입력한다.',
'gt08-c05':'응시 계획을 취소했다는 연락을 받으면 담당자는 취소하려는 교육휴가 요청을 먼저 식별한다. 시험 접수만 취소한 것인지 휴가 신청도 취소하려는 것인지 구분하고,',
'gt08-c06':'응시 계획을 취소했다는 연락을 받으면 담당자는 취소하려는 교육휴가 요청을 먼저 식별한다. 시험 접수만 취소한 것인지 휴가 신청도 취소하려는 것인지 구분하고, 신청자가 아직 결정하지 못한 문의를 확정된 취소로 기록하지 않는다.',
}
# Reviewed equivalent evidence in later procedures. OR alternatives, not new facts.
alternatives={
'gt03-c06':['RM-03@v4의 회사 지급 기기 사용 조건은 정보 정정 과정에서도 유지하며, 지급 여부를 확인하지 못한 기기를 임의로 확인 완료 상태로 바꾸지 않는다.'],
'gt03-c07':['다만 장애를 알렸다는 이유로 RM-03@v4의 회사 VPN 사용 조건이 면제되었다고 안내하지 않으며,'],
'gt03-c08':['다만 장애를 알렸다는 이유로 RM-03@v4의 회사 VPN 사용 조건이 면제되었다고 안내하지 않으며, 공용 컴퓨터를 이용해 내부 문서에 접근하도록 임시 우회 방법을 제시하지 않는다.'],
'gt04-c05':['생일 포인트의 지급 내역을 휴가 승인 기록으로 사용하지 않는다.','생일 축하 포인트 지급 내역은 생일 특별휴가의 신청 번호와 별개로 식별한다. 포인트를 받았다는 문의가 휴가 승인 확인으로 접수되면 문의 목적을 먼저 구분하고, 휴가에 관한 내용은 BD-03@v4의 승인 기록에서 확인한다. 지급 내역 화면을 휴가 승인서 대신 첨부하거나 두 상태를 같은 항목으로 합치지 않는다.'],
'gt06-c05':['일정표에 연차나 재택근무 문의가 포함되어 있으면 TR-02@v4에 따라 별도 항목으로 구분하고, 출장 승인 결과를 그 항목들의 결과로 전파하지 않는다.'],
'gt06-c06':['일정표에 연차나 재택근무 문의가 포함되어 있으면 TR-02@v4에 따라 별도 항목으로 구분하고, 출장 승인 결과를 그 항목들의 결과로 전파하지 않는다.'],
}
# Atomic anchors are located only within the approved article, with original bytes retained.
article_heads=list(re.finditer(r'(?m)^(?:BD|AN|RM|WF|ED|TR)-\d{2} [^\n]+',text))
article_ranges={m.group().split()[0]:(m.start(),article_heads[i+1].start() if i+1<len(article_heads) else len(text)) for i,m in enumerate(article_heads)}
def anchored(article,quote):
 a,b=article_ranges[article];pos=[i for i in range(a,b) if not text[i].isspace()];body=''.join(text[i] for i in pos);needle=''.join(quote.split())
 assert body.count(needle)==1,(article,quote,body.count(needle))
 i=body.index(needle);a,b=pos[i],pos[i+len(needle)-1]+1
 return {'document_id':'hr-handbook','start':a,'end':b,'quote':text[a:b]}
atomic={
'gt01-c02-a1':['입사 후 3개월이 지난 재직자는','생일 특별휴가 1일을 신청할 수 있다.'],
'gt01-c02-a2':['매년 생일 특별휴가 1일을 신청할 수 있다.'],
'gt01-c02-a3':['생일 특별휴가','수습 중인 직원은 대상에서 제외한다.'],
'gt03-c01':['입사 후 1개월이 지난 직원은','재택근무를 신청할 수 있다.'],
'gt03-c02':['보안 교육을 이수하면 재택근무를 신청할 수 있다.'],
'gt03-c04':['재택근무는 매주 최대 2일이며'],
'gt03-c07':['재택근무 시 회사 지급 기기와 회사 VPN을 사용한다.'],
'gt06-c03':['이때 담당자는 전달받은 출장 목적, 출발 예정일, 전달 시점과 접수 확인이 필요한 사유를 임시 기록한다.','임시 기록은 신청 내용을 보존하기 위한 것이며 TR-01@v4의 승인 기한이나 팀장 승인 조건을 없애는 예외로 안내하지 않는다.'],
'gt06-c04':['이때 담당자는 전달받은 출장 목적, 출발 예정일, 전달 시점과 접수 확인이 필요한 사유를 임시 기록한다.','임시 기록은 신청 내용을 보존하기 위한 것이며 TR-01@v4의 승인 기한이나 팀장 승인 조건을 없애는 예외로 안내하지 않는다.'],
'gt07-c03':['임시 기록은','승인 면제가 아니며,'],
'gt08-c01-a1':['여러 날짜의 요청 중 일부만 취소하려는 경우에는','유지하는 날짜와','나누어 기록하고,'],
'gt08-c01-a2':['여러 날짜의 요청 중 일부만 취소하려는 경우에는','취소하는 날짜를','나누어 기록하고,'],
'gt08-c02':['여러 날짜의 요청 중 일부만 취소하려는 경우에는','전체 신청을 일괄 삭제하지 않는다.'],
'gt08-c07-a1':['응시 계획을 취소했다는 연락을 받으면 담당자는 취소하려는 교육휴가 요청을 먼저 식별한다.','다른 시험에 관한 요청이나','일괄 삭제하지 않는다.'],
'gt08-c07-a2':['응시 계획을 취소했다는 연락을 받으면 담당자는 취소하려는 교육휴가 요청을 먼저 식별한다.','이미 별도로 관리되는 휴가 기록까지 일괄 삭제하지 않는다.'],
}
for cid,target in (('gt06-c03','TR-01@v4의 승인 기한이나'),('gt06-c04','팀장 승인 조건을')):
 atomic[cid]=['신청 시스템이 열리지 않거나 제출 직후 오류가 발생하여 접수 여부를 알 수 없는 경우에는 TR-04@v4의 통상 기록을 바로 확인하기 어려울 수 있다.','전달받은 출장 목적,','임시 기록은 신청 내용을 보존하기 위한 것이며',target,'없애는 예외로 안내하지 않는다.']
for cid,target in (('gt07-c01-a1','신청자가 알린 시점,'),('gt07-c01-a2','사용 희망일,'),('gt07-c01-a3','장애 상황을')):
 atomic[cid]=['다만 시스템에 접속할 수 없거나 제출 후 접수 화면이 표시되지 않아 기록 존재를 확인할 수 없는 경우에는 담당자가',target,'임시 기록으로 남기고 이를 접수 확인용으로 안내한다.']
# Procedural paraphrases are partial relevance evidence, never fact OR equivalence.
related_alternatives=alternatives
alternatives={}
questions=read_json(OUT/'questions.json');qh=fingerprint(questions);claims=[];factrows=[]
for q in packet['questions']:
 facts=[]
 for c in q['codex_source_checked']['claims']:
  cid=c['id'];required=cid in q['answer_rubric']['required_claim_ids'];quote=fix.get(cid,c['source']['quote'])
  spans=[anchored(c['source']['article_id'],v) for v in atomic[cid]] if cid in atomic else [span(quote)]
  # These exception statements depend on the previously stated system-outage condition.
  if q['id']=='gt07' and cid not in ('gt07-c01-a1','gt07-c01-a2','gt07-c01-a3'):
   spans.insert(0,span('다만 시스템에 접속할 수 없거나 제출 후 접수 화면이 표시되지 않아 기록 존재를 확인할 수 없는 경우에는'))
  alts=[{'spans':spans}]+[{'spans':[span(s)]} for s in alternatives.get(cid,[])]
  claims.append({'question_id':q['id'],'claim_id':cid,'role':'required' if required else 'supplementary','approved_claim':c['text'],'article_id':c['source']['article_id'],'alternatives':alts,'mapping':'fresh whitespace-insensitive location, exact Unicode source slices; never old offsets','expanded_for_subject_or_condition':cid in fix or q['id']=='gt07','atomic_anchors':cid in atomic,'related_partial_evidence':[span(v) for v in related_alternatives.get(cid,[])]})
  if required:facts.append({'fact_id':cid,'alternatives':alts})
 factrows.append({'question_id':q['id'],'required_facts':facts})
assert len(claims)==57 and sum(len(q['required_facts']) for q in factrows)==38
assert {(r['question_id'],r['claim_id'],r['approved_claim']) for r in audit['rows']}=={(r['question_id'],r['claim_id'],r['approved_claim']) for r in claims if r['role']=='required'}
facts={'schema_version':1,'source_fingerprint':sm['fingerprint'],'questions_hash':qh,'offset_unit':'unicode_codepoint','questions':factrows}
fact_metrics.validate(facts,sm['fingerprint'],qh,questions,docs)
shutil.copyfile(ROOT/'rag_package/resources/sample/llm-local.json',OUT/'llm-preview-only.json')
config={'schema_version':2,'chunking':{'method':'fixed','size_chars':256,'overlap_chars':64},'retrieval':{'method':'bm25','candidate_k':20,'top_k':5,'context_budget_chars':2000,'rrf_k':60},'embedding_config':None,'llm_config':'llm-preview-only.json'}
write_json(OUT/'bm25.json',config)
if not (OUT/'build-bm25').exists():retrieval.build(OUT/'snapshot-installed',OUT/'bm25.json',OUT/'build-bm25')
bm,_,cs=retrieval.load_build(OUT/'build-bm25',retrieval.config(OUT/'bm25.json')[0])
# Provisional all-chunk grades, reviewed below before judgments_complete is set.
judgments={};rows=[]
for q in questions:
 relevant=[c for c in claims if c['question_id']==q['id']];judgments[q['id']]={}
 for i,c in enumerate(cs):
  reasons=[];grade=0
  for cl in relevant:
   for alt in cl['alternatives']+[{'spans':[s],'partial_only':True} for s in cl['related_partial_evidence']]:
    inside=all(c['start']<=s['start'] and c['end']>=s['end'] for s in alt['spans'])
    overlaps=[{'start':max(c['start'],s['start']),'end':min(c['end'],s['end'])} for s in alt['spans'] if min(c['end'],s['end'])>max(c['start'],s['start'])]
    if inside or overlaps:
     value=2 if inside and cl['role']=='required' and not alt.get('partial_only') else 1
     grade=max(grade,value);reasons.append({'claim_id':cl['claim_id'],'role':cl['role'],'relationship':'related procedure, not sufficient fact evidence' if alt.get('partial_only') else 'complete sufficient evidence' if inside else 'partial source evidence requiring other chunk(s)','spans':overlaps})
  judgments[q['id']][c['chunk_id']]=grade
  rows.append({'question_id':q['id'],'chunk_index':i,'chunk_id':c['chunk_id'],'grade':grade,'reasons':reasons})
qrels={'schema_version':1,'source_fingerprint':sm['fingerprint'],'chunk_fingerprint':bm['identity']['chunk_fingerprint'],'questions_hash':qh,'judgments_complete':False,'judgments':judgments}
write_json(OUT/'facts.json',facts);write_json(OUT/'claims-mapping.json',claims);write_json(OUT/'qrels-provisional.json',qrels);write_json(OUT/'qrels-audit-provisional.json',rows)
write_json(OUT/'source-review.json',{'status':'source_read_mapping_prepared_pending_chunk_review','author':'Codex dev','reviewer':'Codex dev (same agent, not independent human approval)','source_pages_read':list(range(1,24)),'approved_required':38,'approved_supplementary':19,'new_canonical_characters':len(text),'new_canonical_sha256':digest(text.encode()),'source_fingerprint':sm['fingerprint'],'chunk_count':len(cs),'judgment_count':len(rows),'retrieval_results_seen':False,'model_calls':0,'snapshot_replay_identical':True})
# Review each nonzero chunk in canonical order, plus full corpus read in the task.
for i,c in enumerate(cs):
 rs=[r for r in rows if r['chunk_index']==i and r['grade']]
 if rs:print(i,c['start'],c['end'],[(r['question_id'],r['grade']) for r in rs],repr(c['text']))
