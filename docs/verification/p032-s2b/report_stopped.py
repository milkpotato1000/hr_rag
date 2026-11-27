"""Model-free audit/report. Does not resume or modify the stopped runner/ledger."""
from pathlib import Path
import importlib.util,json,html,sys
spec=importlib.util.spec_from_file_location('runtime',Path(__file__).with_name('runtime.py'));rt=importlib.util.module_from_spec(spec);spec.loader.exec_module(rt)
from rag_package import chunk_artifact,embedding,reranker,llm,rag
from rag_package.storage import RagError
def deny(*a,**kw):raise AssertionError('stopped report forbids models')
embedding.encode=reranker.score=llm.invoke=rag.ask=rag.compare=deny
E,R=rt.E,rt.RUN;m=rt.read(R/'manifest.json');rt.check_frozen(m)
ledger=rt.read(R/'ledger.json');ledger_hash=rt.sha(R/'ledger.json')
assert ledger['status']=='halted' and ledger['reserved_workers']==1 and ledger['reserved_items']==567 and ledger['active'] is None
op=ledger['operations'][0];assert op['observation']['worker_exited'] is True and op['observation']['resume_safe'] is True
assert op['completed_items'] is None and len(ledger['operations'])==1 and not ledger['gates']
assert not (R/'semantic').exists() and not (R/'comparison').exists()
try:rt.module('control').Control(R/'ledger.json')
except RagError as error:assert error.code=='s2b_not_restartable'
else:raise AssertionError('restart was accepted')
rules={name:chunk_artifact.replay(R/'input/chunks'/name) for name in ('fixed','recursive','structure')}
qs=rt.read(R/'input/questions.json')
rows=[{'method':method,'question_id':q['id'],'question':q['question'],'status':'not_executed','reason':'halted_at_semantic_boundary_before_compare',
       'branch_union':None,'candidate_N20':None,'top_k':None,'contexts':None,'fact_recall':None,'chunk_recall_at_k':None,'MRR':None,'nDCG':None,'answer_quality':None} for method in ('fixed','recursive','structure','semantic') for q in qs]
summary={'status':'halted','S2b_matrix_complete':False,'P032_complete':False,'boundary_attempts':1,'workers_started':1,'workers_exited':1,
         'requested_items':567,'known_completed_items':0,'unknown_completed_jobs':1,'unknown_requested_items':567,
         'worker_returncode':op['observation']['returncode'],'worker_exit_zero_is_not_inference_success':True,
         'original_error':ledger['first_error']['code'],'sdk_import_diagnosis':rt.read(E/'sdk-import-diagnostic.json'),
         'environment_diagnosis':rt.read(E/'installed-file-diagnostic.json'),'rows':rows,
         'search_executed':0,'search_not_executed':40,'comparison_invocations':0,'rule_replay':rules,
         'started_at':ledger['started_at'],'deadline':ledger['deadline'],'RSS_sampled_peak_bytes':op['observation']['sampled_peak_rss_bytes'],
         'replay_model_calls':0,'S1_files_preserved':len(m['files']['S1']),'S2a_files_preserved':len(m['files']['S2a']),'protected_files_preserved':len(m['files']['protected']),
         'retry':0,'next':'Committed intake R20261127-3674f09b; exact follow-up required; no environment repair or model retry performed',
         'forbidden_calls':{'LLM':0,'API':0,'Ollama':0,'Drive':0,'evaluator':0,'reranker':0,'model_download':0,'key_reads':0},
         'holds':'P013/P014/P029 C4/grant unchanged'}
assert rt.sha(R/'ledger.json')==ledger_hash
rt.write(E/'stopped-summary.json',summary)
rt.write(E/'final-checks.json',{'audit_status':'PASS','execution_status':'halted','S2b_complete':False,'worker_reaped':True,'additional_dispatches_after_failure':0,
    'rule_replays':3,'search_rows_not_executed':40,'metrics_all_null':True,'ledger_unchanged_hash':ledger_hash,
    'S1_files':len(m['files']['S1']),'S2a_files':len(m['files']['S2a']),'protected_files':len(m['files']['protected']), 'model_calls_this_audit':0})
esc=lambda x:html.escape(str(x))
text='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>청킹 비교 중단 기록</title><style>body{font:16px/1.6 system-ui;max-width:1000px;margin:auto;padding:24px;background:#f7f8f7;color:#213a32}h1,h2{line-height:1.3}.notice,details{border:1px solid #bdcfc4;background:white;padding:18px;border-radius:10px;margin:16px 0}.notice{border-left:6px solid #a34d26}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere}td,th{text-align:left;padding:9px;border-bottom:1px solid #c9d5cc}table{width:100%;border-collapse:collapse}.table{overflow:auto}:focus-visible{outline:3px solid #a34d26}</style>
<h1>실제 청킹 비교가 시작 단계에서 중단됐습니다</h1><div class="notice"><b>검색 결과 0건 · 미실행 40건</b><p>의미 청킹의 첫 embedding 작업이 SDK 오류로 실패했습니다. 작업 프로세스는 회수됐고, 이후 모델 요청은 차단됐습니다. 고정·재귀·구조의 기존 청크는 보존되어 있지만 이번 검색 비교 결과는 아닙니다.</p></div>
<h2>확인된 원인과 한계</h2><p>최초 오류는 <code>embedding_sdk_failed</code>입니다. 모델을 만들지 않는 후속 SDK import 진단에서 torch가 <code>typing_extensions</code>를 찾지 못했습니다. 설치 폴더의 25개 배포 정보 디렉터리에서 METADATA/RECORD가 없었습니다. 파일이 사라진 원인과 시점은 확인되지 않았습니다.</p>
<p>상위 SDK의 버전 정보와 모델 파일 hash는 사전 검사에 통과했습니다. 그러나 그것만으로 모든 하위 의존 파일과 import 가능성을 보장하지는 못했습니다. 기존 설치 환경은 수정하지 않았습니다.</p>
<h2>실행량을 읽는 법</h2><ul><li>시작한 worker 1개, 요청 단위 567개. 실제 완료 단위 수는 미확정입니다.</li><li>프로세스 exit code는 0이지만 반환 JSON은 오류였습니다. exit0을 추론 성공으로 계산하지 않습니다.</li><li>색인 0회, 질문 검색 0회, compare invocation 0회, 자동 재시도 0회입니다.</li><li>답변·평가기·LLM 청킹·API·Drive 호출도 없습니다.</li></ul>
<h2>네 방식의 10문항 상태</h2><p>모든 검색/사실 회수 지표는 미측정입니다. N/A를 0점으로 채우거나 기존 S1 결과를 새 청킹 비교로 이식하지 않았습니다.</p><div class="table"><table><tr><th>방식</th><th>기존 청크</th><th>검색 완료</th><th>미실행</th><th>품질</th></tr>'''
for method,n in [('fixed',201),('recursive',257),('structure',264),('semantic','경계 생성 실패')]:text+='<tr>'+''.join('<td>'+esc(x)+'</td>' for x in (method,n,0,10,'N/A'))+'</tr>'
text+='</table></div><details><summary>40개 질문별 미실행 기록</summary><pre>'+esc(json.dumps(rows,ensure_ascii=False,indent=2))+'</pre></details><details><summary>실패·회수·원래 deadline 기록</summary><pre>'+esc(json.dumps(ledger,ensure_ascii=False,indent=2))+'</pre></details><h2>다음 단계</h2><p>실패와 기존 환경을 보존한 독립 환경 복구 및 누적 한도 검토를 plan 요청 R20261127-3674f09b로 등록했습니다. 실제 재개는 별도 READY 이후입니다. S1/S2a·정답·보류·grant는 변경하지 않았습니다.</p></html>'
(E/'report.html').write_text(text)
print(json.dumps({'audit':'PASS','execution':'halted','additional_dispatch':0,'not_executed':40,'S1_preserved':len(m['files']['S1']),'S2a_preserved':len(m['files']['S2a'])}))
