# P032 S2d — 기존 로컬 Qwen 4B 실제 답변 생성

2026-11-28 READY. 사용자 최신 지시: “일단 기존 로컬 Qwen 4B로 진행하고, Drive 연결은 보류하자. 지금 규정집으로 실제 답변 생성부터 검증하도록 플랜 잡고 dev에 전달해줘.” 이 결정은 생성 경로 선택 대기를 해소한다. Drive 연결과 P013/P014 평가기는 계속 보류한다. LLM 청킹·API·다른 모델 비교는 이번 실행 범위가 아니다.

## 결과와 선행

S2c 완료 `0ea558018b94b50d29c54fe45cb2ba34616c4356`의 독립 설치 패키지로 현재 규정집의 실제 답변을 생성하고 질문→전달 문맥→답변→원문 대조를 학습 자료로 남긴다. [입력 감사](../reviews/p032-s2d-input-audit.json)는 S1의 10개 질문 artifact 전체590파일과 원문 PDF를 해시 고정한다. [준비 검토](../reviews/P032-s2d-readiness-20261128.md)의 정확 채택 및 아래 사전 검증 후에만 실제 호출한다.

현재 PDF는 `2. Document Chunking/data/source-v4/output/pdf/hr-handbook.pdf`, SHA256 `1a199799cc3807fdaa6e0390784d58697d38a83d4708b2967ddead72dc4f9369`다. 새 문서·GT 수정·파싱·임베딩·검색·리랭커 재실행은 필요하지 않다. S1의 `docs/verification/p032-s1/run001/rerank/none/gt01`부터 `gt10`까지 재사용한다. fixed256/overlap64, E5 Hybrid, 리랭커 none, K5, 문맥 예산2000자이며 실제 문맥은 질문별1280자다. 단일 기준선이며 여러 리랭커/청킹의 답변 비교 완료가 아니다.

## 구현 경로와 동결

기존 `rag-lab answer-from-rerank --run <동결 artifact> --llm-config <새 설정> --out <새 경로> [--execute]`를 사용한다. reranking.load의 artifact/원문 검증, rag.messages_for·business_answer 및 llm.invoke를 그대로 사용한다. 별도 가짜 transport나 직접 요청으로 우회한 응답을 제품 경로 실행으로 표시하지 않는다. 기존 CLI로 충분하므로 새 product CLI/adapter를 만들지 않는다.

새 S2d 전용 실험 runner·ledger·자원 관찰·검증/보고서는 `docs/verification/p032-s2d/`에 작성할 수 있다. 기존 P013 runner/grant/실패 기록은 재사용하거나 변경하지 않는다. 같은 기능의 script를 참고할 수 있으나 전용 제어와 독립 시험으로 검증한다. S2c core-only 설치와 wheel의 hash/import 경로를 확인하여 재사용하며, 없거나 훼손됐으면 같은 검증된 source의 wheel로 별도 core-only venv만 설치한다. SDK·모델 다운로드/전역 설정 변경은0이다.

실제 요청 전 다음을 커밋해 동결한다: 정확 adoption, 설치 wheel/source/환경, 원문과590입력 hash, 10질문·문맥·messages/actual_messages hash, 선택 profile, runner/checker, 요청별 예약 ledger와 한도. answer-from-rerank preview10개를 모델0으로 검사한다. 각 요청은 질문과 기존 선택 문맥 및 제품 system prompt만 포함한다. 정답·facts/qrels·원문 전체·검토 의견은 프롬프트에 추가하지 않는다. prompts/문맥을 결과를 보고 바꾸지 않는다.

## 모델 확인과 서버

기존 alias `qwen3:4b`를 사용한다. 과거 잠금 digest는 `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`, 기록상 HF 원본은 `Qwen/Qwen3-4B-Thinking-2507`, Q4_K_M이다. 이름만 보고 일반 Qwen3-4B와 동일하다고 주장하지 않는다. 이번 /api/tags·/api/show metadata와 runtime version을 기록하고 과거 digest와 대조한다. 불일치·미설치면 생성0으로 중단·접수하며 자동 pull/tag 변경·다른 모델 교체는 하지 않는다. HF 원본/revision의 역사적 설명과 현재 Ollama가 확인한 digest/parameter count를 구분한다.

기존 127.0.0.1:11434 서버를 우선 사용한다. 서버가 없으면 기존 설치된 Ollama로 이 작업 소유 loopback 서버를 최대1회 시작할 수 있다. 다른 프로세스/포트를 강제 종료하거나 기존 서버 전역 환경을 바꾸지 않는다. 기존 서버가 정상 사용 중이면 새 서버를 겹쳐 띄우지 않는다. 새 모델 다운로드·8B 적재·다른 모델 unload는 허용하지 않는다.

사전 /api/ps에서 loaded model0과 다른 실행 작업이 없음을 확인하고 단일 실험 lock을 확보한다. 독점 사용을 확인할 수 없거나 외부 요청/다른 모델이 나타나면 신규 호출을 중지한다. /ps와 로컬 lock만으로 외부 클라이언트 부재가 완벽하게 보장된다고 표현하지 않는다. 사용자 앱을 닫아 자원을 확보하지 않는다.

새 profile은 4B 하나만 정의한다. schema가 요구하는 역할 참조는 같은 profile로 할 수 있지만 실제 호출 role은 generation만 허용한다. response_mode=json_object, temperature=0, seed=42, num_ctx=8192, max_output_tokens=1024, timeout_seconds=180을 고정한다. 기존 adapter의 think=false, keep_alive=0을 유지한다. thinking 모델이 이 조합을 지원하는지는 검증 대상이다. unexpected_thinking/잘린 응답/JSON 실패를 성공으로 바꾸기 위해 hidden thinking을 저장·절단하거나 parser를 완화하지 않는다.

8192는 이번 설정값이며 모델 고유 최대 문맥이라는 뜻이 아니다. preview body bytes와 문자 수, 관측 input/output token을 기록한다. 정확한 사전 tokenizer 계산이 없으면 미측정으로 표시한다. 문맥1280자 외 system/질문/ID overhead를 포함하며 조용히 입력을 잘라 통과시키지 않는다.

## 실행량과 자원 한도

- 실제 생성은 gt01→gt02 smoke 후 gt03~gt10 순서, 질문당 최대1회·전체10회. smoke2회는 전체10회에 포함한다. 병렬1, retry/fallback/warmup/빈 preload0. 예약 후 실패·timeout도 사용한 시도로 남기며 미사용 한도를 다른 단계로 전용하지 않는다.
- 처음 실제 dispatch 직전부터 전체45분 wall cap. 개별 HTTP180초 및 독립 watchdog210초, 요청 뒤 정리 관찰60초. deadline은 ledger 재개로 초기화하지 않는다. 모델 없는 준비는 별도 구간이다.
- metadata(/tags,/show,/ps,/version)는 총200회 이내·개별5초, 역할별/endpoint별 횟수 기록. /ps 정리 관찰은5초 간격. 기존 adapter의 요청 전후 digest 조회도 포함한다. 모델 unload용 빈 POST나 별도 제어 추론은0이다. 정상 요청의 keep_alive=0 이후 /ps에서 해제 여부를 관찰한다.
- 사전 디스크2GiB 이상,30초간 OS pressure normal 및 핵심 계측 정상 확인. 적재부터 요청 종료/정리까지1초 간격 OS pressure와 Ollama 서버·runner의 합산 RSS를 기록한다. RSS8GiB 초과, critical pressure(level>=4), OOM, 핵심 계측 불능이면 중단한다. 이는 4B 실험의 보수적 운영 한도이며 실제 최소 메모리 스펙이나 hard memory sandbox가 아니다.
- warning 발생 시 신규 호출을 막고 현재 요청의 실제 상태를 보존한다. 요청 후 normal30초를 최대60초 안에 확보하지 못하면 inconclusive로 종료한다. 호출마다 모델 해제 여부를 확인하고 다른 모델과 동시 적재하지 않는다. RSS 표본 최고값과 통합 메모리/GPU 실사용을 동일시하지 않는다. swap·vm_stat·loaded size/context 지원 필드는 별도로 기록한다.
- timeout/중단 시 client 종료가 Ollama 추론 취소를 입증하지 않는다. dispatch 시도/응답 완료/서버 모델 상태를 분리하고 미확정 작업이 있으면 다음 요청0, 자동 재시도·unload0으로 남긴다. 소유 client/새로 시작한 전용 서버만 소유권을 확인해 정리할 수 있다. 기존 공유 서버나 외부 프로세스를 강제 종료하지 않는다.
- runner는 중복 실행,10회 초과, deadline 초과, metadata cap, identity 불일치, pressure/RSS 실패, timeout 후 다음 dispatch 금지, 실패 ledger 보존을 가짜 transport/process로 독립 시험한다. 시험은 실제 모델/서버 호출0이다. 위 제어가 검증되기 전 실제 요청하지 않는다.

## 2문항에서 10문항으로 확대하는 기준

각 smoke의 provider 완료, strict JSON/업무 schema, 인용 ID/원문 slice, 모델 identity 전후, 자원·요청 상태가 모두 검증돼야 한다. dev는 아래 내용도 고정 원문·승인 GT와 직접 대조해 기록한 뒤에만 나머지8개를 시작한다. 이 검토는 별도 Qwen judge/claim extraction/NLI를 호출하지 않는다.

- gt01 문맥은 필수6/6을 포함한다. 재직3개월 경과, 연간1일, 수습 제외, 생일이 속한 달, 근무일 사용, 사용3영업일 전 신청을 정확히 답하는지 확인한다.
- gt02 문맥은 필수3/3을 포함한다. 최대5일 이월, 다음 해3월31일, 생일 특별휴가 제외를 구분한다.
- 원문과 충돌하거나 근거 없는 조건·금액·예외를 만들지 않는다. 보충 정보 생략 자체는 실패가 아니며 추가한 내용은 검증한다. 조건 없는 광범위한 허용으로 바꾼 표현도 실패로 기록한다.
- 두 smoke 중 하나라도 기술/자원/내용 검토 실패면 자동 확대하지 않는다. 같은 입력 재호출·prompt 튜닝을 즉석에서 하지 않고 실패와 원인을 보고한다. 이 경우 10문항 완료/4B 품질 통과라고 표시하지 않는다.

전체 구간도 기술/자원 실패는 즉시 중단한다. gt03~gt10의 내용상 오류는 결과를 그대로 기록하며 나머지 질문은 같은 동결 조건으로 계속해 실패 유형을 관찰할 수 있다. 전체 품질은 실패가 하나도 없다는 가정으로 작성하지 않는다.

## 답변 대조와 학습 보고

질문별로 (1)전달 문맥의 필수 fact 회수 (2)실제 답변의 필수 내용 포함/정확성 (3)추가 정보의 지지 여부 (4)인용의 형식·원문 일치와 의미적 지지 (5)보류 적절성 (6)지연·token·자원·실패/미확정을 분리한다. 필수/보충 구분과 GT는 바꾸지 않는다. 검토 주체는 dev Codex 원문 대조임을 표시하며 사람 승인이나 독립 gold 평가를 새로 받았다고 주장하지 않는다. 자동 Faithfulness/Correctness/NLI 점수는 만들지 않는다.

특히 gt03은 문맥3/8, gt08은2/8만 회수되어 있다. 빠진 정답을 보고 답변에 주입하지 않는다. 검색 단계 누락과 전달된 근거를 생성기가 누락/왜곡한 경우를 분리하고, 부족한 문맥에서 적절한 부분 답변/보류를 정답 전체 완성 실패와 함께 설명한다. gt09/gt10은 필수 fact0/N/A이나 관련 청크5개가 존재한다. 전기요금 한도·유류비 단가를 발명하지 않고 근거 부재를 설명하는지 실제 출력으로 확인한다. N/A를1점으로 바꾸지 않는다.

보고서는 질문→동결 문맥/원문→실제 답변/인용→검토→접힌 실행 로그 순서로 제공한다. 원문 출처·설정·버전·artifact hash·실패·검토 한계를 재현 가능하게 남긴다. 기존 UI가 지원하는 저장 결과 재생 또는 별도 읽기 전용 HTML로 확대 가능한 답변/근거를 보여준다. UI 검증은 모델 실행 권한을 끄고 수행하며 P029 filepicker 차단을 우회하지 않는다. 새 학습 가이드를 현재 학습 목차에 연결한다.

## 완료와 인계

정확 채택→전용 제어 독립 시험→설치/입력/profile 동결→metadata/사전 자원→smoke2→조건부 잔여8→원문 대조/보고→필요 회귀·guard→증거 커밋/정상 personal/dev push 순서다. 기술 검증 완료와 답변 품질의 관찰 결과를 분리한다. 실패 시 재실행 허가를 만들어내지 않고 중단 상태·미완료 범위를 남긴다. runtime 결함/새 정책이 필요하면 기존 실패 보존 후 intake한다. main/PyPI·Drive·LLM 청킹·API·8B·평가기/기존grant는 제외한다. S2d가 끝나도 전체 P032/goal 완료가 아니다.
