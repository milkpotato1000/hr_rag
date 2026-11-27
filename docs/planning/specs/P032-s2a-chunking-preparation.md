# P032 S2a 청킹 비교 사전 준비

2026-11-28 DRAFT. S1 최종 산출물·dev 전달 확인과 별도 준비 검토/정확 채택 전 실행하지 않는다. 실제 semantic/LLM 경계 추론·검색·답변 비교는 후속 계약이며, 이 준비가 다섯 방식의 실제 비교를 대체하지 않는다.

## 목적과 선행

사용자의 모델·청킹·검색·리랭커 선택 비교 목표에서 남은 청킹 축을 준비한다. 생성 profile 선택과 Drive 링크 답변을 기다리되, 해당 선택에 의존하지 않는 원문·경계·작업량 준비를 분리한다. P032 S1의 원문·질문·facts 및 실제 E5 준비 결과를 그대로 읽고, 기존 S1 ledger/deadline/73worker 사용량을 재설정하거나 재사용하지 않는다. P013/P014·P029 C4 보류는 유지한다.

S1의 최종 커밋/설치물/보고서와 보존 파일 감사가 확인된 후 새 `docs/verification/p032-s2a/` 증거 및 별도 비공개 작업 디렉터리에 생성한다. 설치된 CLI와 동일 코어를 사용하고 개발 소스 우연 import를 배제한다. 기존 run001/continuation001, 승인 GT, qrels, PDF와 canonical은 수정하지 않는다.

## 고정 입력과 설정 후보

- S1의 새 generic snapshot을 복사·검증하여 source fingerprint를 유지한다. PDF 재작성·재파싱·원문 정규화 변경은 하지 않는다. source와 canonical/페이지/제목 mapping hash를 기록한다.
- 기존10개 질문과38개 필수 fact/span은 나중 비교의 읽기 전용 입력으로 연결한다. query/GT/qrels를 청킹 경계 입력에 넣지 않는다.
- fixed/recursive/structure의 공통 size256문자, overlap64문자. 세 방식의 overlap 의미 차이는 유지하고 같은 알고리즘이라고 표시하지 않는다.
- semantic 후보는 size256/overlap64, unit_max_chars120, minimum_chars120, distance_threshold0.35, S1 E5-small 고정 revision/profile이다. 이는 통제 실험 시작 설정이며 최적값/검증 성능이 아니다.
- LLM 후보는 size256/overlap64, unit_max_chars120, window_max_chars1200, window_max_units20, max_windows64, max_prompt_bytes16384이다. 준비 단계에서는 패키지의 명시적 미설정 local/API 예시 profile로 요청 형식·작업 수만 preview한다. 실제 모델·digest·API 자격 선택으로 간주하지 않으며 실행 가능한 profile로 승격하지 않는다.

샘플 예시와 실제 S1 E5 profile의 출처를 구분한다. LLM profile의 validation_status/미설정 표시를 통과시키려고 지우지 않는다. 예시 profile로 preview가 불가능하면 그 구체 이유를 남기고 실제 계정/서버를 조회하지 않는다.

## 허용 작업과 금지 호출

규칙3종은 실제 deterministic chunk artifact를 만든다. semantic/LLM은 `chunk`의 기본 preview만 저장한다. E5 파일 identity 확인과 tokenizer/모델 설정 JSON 읽기는 가능하나 모델 인스턴스·embedding worker·LLM 실행은 하지 않는다. 로컬/API preview의 provider별 body/template 차이를 표시하되 정확 tokenizer 측정이 없으면 token count는 null이다.

model/inference/download/API/Ollama/Drive/OAuth 요청0, 키 읽기0, 모델 server 시작·종료·pull0. `--execute-chunking`, `--execute-retrieval`, `--execute`를 사용하지 않는다. 새 index·질문 embedding·reranker 호출도 없다. 현재 소유한 모델을 unload하거나 타 프로세스/캐시를 정리하지 않는다. 기존 S1 실행 runner나 P013 grant를 가져오지 않는다.

사전 한도 오류는 그대로 기록한다. unit/window가 설정 한도를 넘으면 단위·원문을 몰래 삭제하거나 자동으로 크기/상한을 바꾸지 않는다. 새 후보 설정이 필요하면 이유와 예상 작업량을 계획 검토로 되돌린다.

## 검토 결과에 필요한 것

1. 세 규칙 artifact의 chunk 수·길이 분포·중복 문자·원문 coverage·강제 분할·페이지/heading 경계와 재생 identity. 전체 원문 누락/중복의 정책적 의미를 구분한다.
2. semantic unit 수·단위 길이·문서별 순서·profile max_chunks 적합성과 예상 경계용 embedding1job. 경계가 아직 없으므로 최종 청크 수·새 색인 workload는 미확정/상한으로 표시한다.
3. LLM의 정확 window 수, 각 unit 수/원문 문자/실제 request bytes, 요청 fingerprint와 미측정 토큰. provider 예시별 preview 차이를 기록하고 실제 결과/안정성이라고 쓰지 않는다.
4. gt01 자격·연간 일수·수습 조건, gt03 여러 하위 질문, gt06 다중 구간 facts, 목차의 출장 제목이 생일 본문 청크에 붙는 기존 사례를 원문과 함께 보여준다. 세 규칙의 경계만으로 관찰 가능한 분리/포함을 설명한다. query를 모델 경계 선정에 사용하지 않는다.
5. 각 규칙의 source fact가 단일 청크에 담기는지 또는 몇 개 구간의 합집합이 필요한지 참고 표를 만든다. 이것은 검색 결과나 fact recall 점수가 아니다. 모든 청크를 합친 coverage를 검색 성공으로 보고하지 않는다.
6. S1의 fixed 청크와 새 fixed artifact의 interval/text를 대조한다. 동일하면 재사용 가능한 부분을 hash로 증명하고, artifact/version 차이가 있으면 이유를 기록한다. 기존 chunk qrels는 다른 fingerprint에 복사하지 않는다. 후속 비교는 source facts를 유지하고 새 qrels 필요 여부를 별도로 정한다.
7. 후속 실제4방식(fixed/recursive/structure/semantic) 비교의 예상 작업량을 산출한다. E5 Hybrid·N20·K5·예산2000·질문10개를 고정하고, 경계 embedding/최종 chunk index/query job를 분리한다. 기존 결과 재사용 가능성은 증명된 identity 범위만 반영한다. LLM 방식·답변 모델 비교는 선택 대기로 남긴다.

## 검증과 전달

명시적 network/model entrypoint 차단 하에서 preview·규칙 build·replay가0호출인지 검증한다. 기존 패키지의 관련 성공/거부 동작을 사용하고 새 제품 기능이 필요하면 intake한다. 전체 패키지 재시험을 무조건 반복하지 않으며 새 코드/실패가 있으면 영향을 받는 검증을 수행한다. 원문·기존1513보존 파일·S1 evidence/ledger hash, 선택 profile과 private path/비밀의 공개 범위도 확인한다.

결과 요약에는 준비 완료/제약/미확정 입력·실제 호출0을 표시한다. 학습 안내의 다음 실습에서 fixed·recursive·structure의 실제 경계와 semantic/LLM preview를 명확히 구분한다. 저장 결과를 모델 없이 재생하고 UI가 있는 경우 동일 원문/경계 표시를 허용 경로에서 확인한다. P029의 차단된 filepicker 검증은 우회하지 않는다.

dev는 증거와 후속 작업량을 커밋·정상 personal/dev 전달한 뒤 멈춘다. plan은 이 결과로 실제 청킹 비교의 자원·시간·누적 상한을 별도 READY에서 확정한다. S1의 종료가 새 실제 호출의 자동 허가는 아니며, 이 준비만으로 P032 C2/C3나 전체 goal을 완료하지 않는다.
