# P032 S2b 실제 청킹 4방식 비교 초안

2026-11-28 DRAFT. S2a의 커밋된 완료 증거와 최종 수치/설치 identity를 검토한 뒤 별도 READY·정확 채택이 필요하다. 이번 문서는 실제 모델 호출 허가가 아니다. LLM 청킹과 답변 생성의 사용자 선택 대기를 우회하지 않는다.

## 비교 목적

같은 원문에서 fixed/recursive/structure/semantic의 실제 경계를 만들고, 동일 E5 Hybrid 검색으로 질문별 필요한 근거가 후보→top K→전달 문맥의 어느 단계에서 빠지는지 비교한다. 이4방식의 완료가 전체5방식/LLM 답변/Drive 목표 완료는 아니다. S1 검색·리랭커 검증은 보존하고 별도 실행으로 관리한다.

## 입력·통제 조건 후보

- S2a와 S1의 동일23쪽 규정집 snapshot/source fingerprint·10질문·38필수 fact/span을 hash로 고정한다. 파싱/원문/GT를 수정하지 않는다.
- 규칙3종은 S2a 저장 artifact를 그대로 사용한다: fixed201, recursive257, structure264개. 현재 관찰값이며 커밋된 완료본에서 재확인한다.
- semantic은 S2a의567개 unit, unit_max120/minimum120/threshold0.35, size256/overlap64 설정과 고정 E5-small profile을 사용한다. 저장 float32 unit vectors로 최초 경계를 계산하고 경계 이유/거리/강제 분할을 표시한다. 최종 chunk 상한567개다. 실제 품질을 본 뒤 임계값을 바꾸지 않는다.
- 검색은 E5 Hybrid/RRF60, branch top20/최종 후보N20, K5, 문맥2000문자, 같은 질문을 사용한다. 리랭커는 실행하지 않고 생성은 preview다. embedding CPUfloat32/batch1/token512, worker300초는 S1과 같다.
- 네 방식 모두 새 v3 입력으로 구성한다. S2a fixed의 chunk bytes는 S1과 같지만 frozen artifact fingerprint가 다르므로 S1 index/query/qrels를 자동 이식하지 않는다. 같은 새 v3 경로를 검증하는 fixed control을 포함하여 비교한다. S1 결과는 별도의 과거 참고선으로 유지한다.

## 후보 실행량과 한도

S2a 현재 workload에서 보수적 최대45 embedding workers다: semantic unit 경계1 + 최종 chunk index4 + query40. 항목 수 상한은 semantic unit567, index합1289(201+257+264+567), query40으로 총1896이다. 실제 semantic chunk가 줄면 index항목도 줄어들지만 worker 예산을 다른 실험으로 전용하지 않는다. 다운로드/변환0, reranker0, LLM/API/Ollama/Drive/평가기0, 키읽기0, 자동재시도0이다.

새 run의 최초 실제 작업 전에 별도 시작 시각과 전체1시간 deadline을 고정하는 안을 검토한다. 단일 owned worker, RSS4GiB, OS pressure normal, 기존 관찰 불가·warning/critical·timeout·취소 시 owned worker 종료/회수와 추가 작업 중단을 유지한다. S1의 원래 deadline과73회 기록을 수정하거나 새 예산으로 덮지 않는다. 실제 실행 범위/최종 한도는 READY에서 확정한다.

새 semantic 경계가 저장되면 모델0 검증(원문 보존·unit/vector/경계 identity·거리/강제 분할·최대길이·replay)을 먼저 통과한다. 이후 각 variant의 index와 gt01/gt02를 먼저 실행하고, 그 결과의 구조/자원/identity/성공을 확인한 후 나머지8질문을 진행한다. 앞의2질문은 전체10개에 포함하며 중복 재호출하지 않는다. 품질이 낮다는 이유만으로 결과를 버리거나 좋은 variant만 전체 비교하는 선택은 하지 않는다. 기술적 실패/한도 초과는 그대로 보존하고 실제 후속 호출을 멈춘다.

## 비교 지표와 검토

source facts의 후보N20/topK/문맥 recall·all_required·fulfilled ID·유효 분모를 보고한다. 현재 chunk_compare.facts_for의 `candidate`는 Hybrid branch union 전체(최대40개)이므로 이를N20이라고 바꿔 부르지 않는다. 원래 필드는 branch_union으로 해설하고, 보고서에서 저장된 합친 순위의 앞20개로 candidate_N20을 별도로 계산한다. 패키지의 기존 지표 의미를 몰래 변경하지 않는다. gt09/gt10의 fact recall은 N/A다. 다른 청크 fingerprint의 S1 qrels를 재사용하지 않으므로 새 chunk relevance 주석이 없는 이번 비교의 Recall@K/MRR/nDCG는 N/A로 둔다. source fact recall과 chunk Recall@K를 같은 이름으로 표시하지 않는다. Faithfulness/Correctness·답변 품질도 미측정이다.

각 방식의 chunk 수/길이/중복·경계 원인, model boundary 비용과 색인/query 비용, cold latency·관측 RSS, 새 요청과 저장 재생0호출을 구분한다. gt01·gt03·gt06의 조건/예외·다중 구간 근거와 목차/heading 혼입을 같은 원문에서 대조한다. semantic 방식이 규칙보다 낫다는 결론을 미리 정하지 않는다. 경계가 길이 한도로 강제되는 비율도 공개하여 모델이 실제 결정한 부분을 설명한다.

## 구현·검증 준비 항목

기존 설치 CLI/코어/owned-worker 관찰을 사용한다. stage별 새 ledger와 dispatch 전 예약, 항목/worker/시간/실패/미확정 관리가 필요하면 별도 runner로 구현하며 S1 runner/evidence는 불변으로 둔다. 초과 요청·deadline·불명확한 worker·source/profile/artifact 변조·일부 실패 후 자동 재개 거부를 모델 없는 독립 시험으로 검증한다. 기존 source-free 설치물과 SDK·실제 model 파일 hash를 재검증한다. 이 초안 때문에 모델을 추가 다운로드하거나 설치 버전을 바꾸지 않는다.

현재 rag.compare는 variant/질문별 오류를 저장하고 반복을 계속할 수 있다. 실험 runner는 worker exit0만 성공으로 보지 말고 SDK JSON 오류·실패 결과·저장 오류에서도 영구 halted를 기록해 이후 dispatch를 거부해야 한다. 상위 compare가 실패 행을 추가 기록하는 것과 실제 worker가 재시작되는 것을 구분한다. 거부 뒤 실제 호출0을 독립 시험으로 확인한다. 앞2질문 검토·나머지8질문 진행과 설치 comparison/replay를 같은45회 안에 연결할 방법을 READY 검토에서 확정하며, CLI 검증 때문에 전체 호출을 다시 반복하지 않는다.

결과는 저장된 실제4방식 비교 보고서와 설치 UI에서 원문→단위/경계→청크→후보→전달 문맥으로 읽을 수 있어야 한다. source 없는 설치 경로와 입력 fingerprint, 모델0 replay, 허용 desktop/narrow/keyboard 관찰 및 학습 안내를 남긴다. P029 filepicker 차단은 우회하지 않는다. 기존1513보존 파일과 S1/S2a 전체 산출물 hash를 검사하고 정상 personal/dev에 전달한다.

S2a 완료본에서 수치·실패·조건을 대조하고 이 초안을 실행 계약/준비 검토로 확정하기 전에는 dev에 실제 실행을 시작시키지 않는다. LLM34window 실행·답변 모델 비교·사용자 Drive 문서는 별도 선택/계약으로 남긴다. 이 단계의 완료 조건을 전체 goal로 축소하지 않는다.
