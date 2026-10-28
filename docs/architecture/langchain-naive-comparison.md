# P011 Naive 구현 비교와 채택 판정 계약

이 문서는 [P011](../planning/plans/P011.md)의 필수 계약이다. 직접 구현 A와 LangChain 후보 B의 차이를 구현 구조로 한정하고, 모델 출력 변동과 품질/속도 차이를 분리한다. 준비 기준일은 2026-10-28이다.

## 사전 고정과 보존

기준 dev SHA: `58e8eb793b95c524c256c0206e37aa15ff99c6ff`. P009의 `docs/verification/p009/`와 `1. Naive RAG/LEARNING_GUIDE.md`를 참고하되 과거 한 번의 실행을 이번 A 반복 실행 대신 사용하지 않는다.

후보: `1. Naive RAG/variants/langchain/`. 원래 Naive 폴더는 A 기준선으로 보존한다. 후보의 direct 경로는 원본 `rag.py`와 관련 순수 함수/경계의 동일 사본이며, root A와 후보 direct의 replay/대표 실제 실행을 대조한다. 후보 `rag_langchain.py`에서 실제 단계 구성을 바꾼다. 부모/다른 단계 import 없이 후보만 임시 경로로 복사해 회귀·대표 실제 질의를 실행해야 한다. 고정된 외부 로컬 모델 서비스의 사용은 가능하되 재사용 사실과 사본의 색인·데이터 경로를 밝힌다.

1. 구현 전에 원본 파일 inventory/hash, corpus/질문/qrels/source map/프롬프트/runtime/generation lock, Qdrant collection·ID/vector/payload/settings hash를 저장한다. 원래 `.venv`와 `.runtime`을 수정·삭제하지 않는다.
2. 후보 환경은 Python3.12.14 + 기존 requirements.lock pins + langchain-core1.7.0을 사용한다. `requirements-langchain.lock`에 전이 의존성 전체 버전/배포 hash와 원래 환경과의 diff를 남긴다. 기존 pin 유지로 설치할 수 없다면 plan 재검토 대상이다. 최초 import/구성 smoke 전 실제 모델 비교를 시작하지 않는다.
3. A/B 비교 색인은 기존 벡터를 보존한 일관된 사본 또는 동일 collection export/import로 준비한다. 원본 live DB를 무단 복사하지 않는다. 같은 청크를 새로 임베딩해 생긴 차이를 LangChain 효과로 간주하지 않는다. 원본 인덱스는 보존하고 A/B 사본 ID/vector/payload/settings를 대조한다. Qdrant 파일 잠금은 직렬 접근/분리된 사본으로 처리한다.
4. 후보의 기존 runtime-lock은 기준 출처로 보존한다. 설치 검증이 전체 기존 lock hash에 묶여 있으면 후보 전용 환경 lock/검증을 추가하되 runtime/model 조건을 완화하지 않는다.
5. `docs/verification/p011/protocol.json`과 `rubric.json`을 **첫 A/B 모델 실행 전에 커밋**한다. 질문·필수 사실/금지 주장·검색 근거·판정식·K/예산·실행 순서·반복 횟수·모델/라이브러리/데이터 hash를 고정한다. 수정 시 새 protocol 버전으로 같은 양쪽을 재평가하며 원본 결과를 남긴다.

정식 벤치마크 A는 원래 폴더와 원래 격리 interpreter를 사용하고 B는 후보 폴더와 후보 interpreter를 사용한다. 모델 서비스는 동일한 고정 런타임을 직렬 재사용한다. 후보 UI의 direct 사본은 동일성 관찰용이며 후보 환경의 추가 패키지/import 영향을 받을 수 있으므로 그 UI 시간만으로 원래 A의 성능을 대체하지 않는다. 환경·실행 경로·계측 wrapper 차이를 결과에 표시한다.

## 고정 평가 세트

기본값은 K=5, 검색 근거 예산8000문자, timeout120초, 기존 lock의 생성 옵션이다.

| 세트 | corpus / 검색기 | 질문과 목적 |
| --- | --- | --- |
| 기존14 | synthetic15 / Dense | 기존 queries.jsonl q01~q14 그대로. 이미 관찰된 회귀/tuning 자료 |
| 식대 회귀1 | synthetic15 / BM25 | 기존 q10. P009 BM25 사례 재확인 |
| PDF 회귀1 | source-v2 fixed400/80 / Dense | source-evaluation q06. 최대5일·다음해3월31일·생일휴가 제외 및 PDF 원문 byte |
| 추가 확인 c01 | synthetic15 / BM25 | “교육 휴가는 누가 신청할 수 있고 연 며칠이며, 연차·생일 휴가와 어떻게 관리되나요?” 필수: 직무 관련 자격시험 응시자/연1일/별도관리(training-time) |
| 추가 확인 c02 | synthetic15 / Dense | “등록한 자택에서 이사했다면 재택 시작 전에 무엇을 누구에게 요청하나요?” 필수: 등록자택 제한/시작 전/인사 담당자/등록주소 변경(remote-address) |
| 추가 확인 c03 | synthetic15 / BM25 | “출장은 언제까지 누구의 승인을 받아야 하고, 승인받으면 재택이나 휴가도 승인되나요?” 필수: 출발5영업일 전/팀장/휴가·재택 자동승인 아님(travel-approval) |
| 추가 확인 c04 | synthetic15 / Dense | “회사 주택자금 대출의 한도와 금리는 얼마인가요?” 근거 없는 질문; 금액/금리/제도 부재를 단정하지 않고 보류 |

총20개 case다. 추가4개는 사전 고정한 확인 질문이며 충분한 독립 holdout이나 일반 성능 보장의 표본이라고 부르지 않는다. 기존14의 필수 사실은 qrels가 아니라 원문/P009 의미 검토를 근거로 항목화한다. 특히 q03 연1일·자격/신청/기간, q07 제외 직무·팀장 승인, q08 회사 기기/VPN·공용PC 금지, q09 별도 신청/승인과 선택 인용의 주장 지지를 구분한다. 검색 실패로 문맥에 없는 필수 사실을 모델이 추측하도록 요구하지 않는다. 전달되지 않은 사실의 누락은 검색/문맥 실패로 분류하고 생성 평가에 문맥 충분성도 표시한다.

## 비교 순서와 허용 변동

### 1. 모델 없는 계약 검사

- 두 retriever로 기존14+추가4를 K=1/5/100, 예산=1/8000/24000에서 비교한다. PDF q06은 양쪽 검색기로 K5/예산8000에서 비교한다. 무문맥·부족 후보·예산으로 전체 청크 제외를 포함한다.
- 같은 corpus/index/질문 벡터 입력의 ID/순서는 정확히 같아야 한다. BM25 점수는 동일 float 값, Dense 점수는 `abs_delta <= 1e-8 + 1e-7*abs(A)`만 수치 오차로 허용한다. 이 허용치로 순위 변화나 ID 차이를 면제하지 않는다. 고정 벡터 replay와 실제 query embedding 입력/출력 검사를 분리한다.
- 선택/제외 항목·이유·context_chars·snapshot 본문·messages 문자열·model/format/options/think/stream은 동일해야 한다. 실제 HTTP 경계의 직렬화 payload를 캡처해 trace와 맞춘다. 시간·요청 ID·사본 절대 경로만 비교 제외 목록에 사전 명시한다.
- 동일 fake provider 원응답을 양쪽에 replay해 최종 답변/인용/보류·오류가 같은지 본다. 원문 공백/줄바꿈·잘못된/중복/미전달 ID·추가키·생성 오류·timeout·stale index·모델 digest 변경·연속/동시 요청 격리를 독립 기대값으로 검사한다. 성공 데이터만 양쪽 구현에서 공유해 맞추는 테스트로 대체하지 않는다.
- trace의 generation_calls와 실제 `/api/chat` dispatch를 각각 계수한다. no_context dispatch0, 나머지 최대1. 예외가 호출 전 발생하면 시도와 전송을 구분한다. LangChain callback/계측을 켜도 재시도·숨은 생성이 생기지 않아야 한다.

### 2. 실제 의미 품질

20개 case × 3회 × A/B = **120개의 평가 실행 슬롯**을 수행한다. no_context의 생성0회는 그대로 기록한다. seed는 기존42를 고정하고 비교용 별도 순서 seed로 case 순서를 고정한다. 각 쌍은 A→B와 B→A를 round/case에 따라 교대로 배치해 전체 선행 순서가 균형을 이루게 한다. 같은 runtime에서 직렬 실행하며 캐시/동시부하 상태를 기록한다. 결과를 보고 좋은 실행만 고르거나 한쪽만 재실행하지 않는다.

각 결과를 원문에 대조해 필수 사실 충족 수/전체, 전체 필수 사실 충족 여부, 모순·허구 주장 수, 선택 인용이 답변의 각 주장을 지지하는지, 적절 보류/과도 보류, 오류/timeout으로 기록한다. 생성 모델 자기평가를 정답으로 쓰지 않는다. Codex가 원문과 답변을 대조하고 판단 근거/검토 주체를 남긴다. 애매한 주장은 미확정으로 표시해 채택 통과로 세지 않는다. 전체 JSON/ID 통과율, quote byte 일치율은 의미 평가와 별도다.

**ADOPT_LANGCHAIN의 품질 기준:** 모든 case 각각에 대해 3회 합계 필수 사실 충족률·완전 정답 횟수·주장 인용 지지율·적절 보류 횟수가 A보다 낮지 않고, 과도 보류·오류·모순·허구 주장 횟수가 A보다 많지 않아야 한다. 질문 간 이득으로 다른 질문의 저하를 상쇄하지 않는다. 새롭게 발생한 근거 없는 질문의 허구 답변이나 출처 밖 인용은 1회도 허용하지 않는다. 모델 응답 문자열/문장 순서의 차이는 위 의미 기준이 같으면 허용한다. 기준선의 기존 의미 실패를 숨기거나 LC 리팩터링에서 프롬프트를 고쳐 해결하지 않는다.

변동/판단 불확실성으로 결론이 안 나면 INCONCLUSIVE로 기존 구현을 유지한다. 관찰된 기준 미달은 먼저 KEEP_DIRECT로 기록한다. 원인을 수정하고 재평가하려면 양쪽의 영향받는 전체 case/반복을 같은 protocol 버전으로 수행하며 최초 실패를 보존한다. 임계값을 사후 완화하지 않는다. 작은 표본의 이 판정은 “이 고정 실험에서 관찰된 저하 없음”이며 통계적으로 모든 질문에 대한 동등성을 입증한 것이 아니다.

### 3. 속도·자원 비교

120개 평가 슬롯에서 각 단계 시간을 함께 기록한다. 성능 요약에서 오류/timeout을 삭제하지 않고 성공/실패 수와 timeout 경과를 별도 표시한다. baseline에서 측정할 수 없는 세부 구간은 missing으로 표시하며 임의로0을 넣지 않는다.

- client 왕복, Python 실행 전체, 시작/import, index open, query embedding, search, context 구성, generation HTTP, provider load/prompt_eval/eval/total duration을 구분한다. 전체 벽시계와 서로 겹치는 하위 시간을 합산하지 않는다. 외부 wrapper/proxy 계측은 양쪽에 대칭 적용한다.
- warm: 동일 workflow를 사전1회 실행한 상태와 round 순서를 남긴다. 현 runtime의 최대 로드 모델 수 설정 때문에 Dense에서 BGE/Qwen 교체 로드가 일어날 수 있으므로 “둘 다 메모리 상주”라고 가정하지 않고 매번 실제 load_duration을 기록한다.
- process/model cold: 식대BM25, q03Dense, PDFq06Dense의3개 case에 각각3쌍, 총18슬롯을 추가한다. 각 A와 B 실행 전 같은 소유 runtime 재시작/모델 비상주 상태를 확인한다. OS 파일 캐시까지 비웠다고 주장하지 않는다. 다른 사용자의 runtime/포트를 강제 종료하지 않으며 통제 불가하면 cold 결과는 측정불가로 남기고 C4 완료 전에 재현 조건을 확보한다.
- case별 paired delta/비율, 중앙값·min/max와 전체 분포를 제공한다. 3회 표본의 p95나 유의성을 과장하지 않는다. cold/warm·retriever·corpus를 섞어 단일 속도 개선률로 표시하지 않는다.
- 설치 패키지/환경 크기, import 시간, 비교 실행 프로세스 peak RSS(측정 도구/단위), 기존 모델 서비스의 자원 공유 여부를 보고한다. 새 의존성 비용은 품질 점수와 별개다. 속도 향상은 채택 성공의 전제도 결론도 아니다.

실제 생성은 준비/대표 UI/CLI smoke와 수정 후 반복을 포함해 최대320 dispatch를 로컬 실행 범위로 둔다. 실행 ledger에서 평가/워밍업/제어 요청을 구분하고 예상치와 실제 횟수를 남긴다. 초과·대량 sweep·새 모델·유료 API는 별도 범위 검토다. timeout을 무한 retry로 메우지 않는다.

## UI·CLI/API와 재현

후보 `--implementation direct|langchain`과 `/api/ask` implementation을 연결한다. 입력 생략은 direct로 고정하고, UI는 판정 파일의 추천을 표시하되 사용자 선택을 숨겨 바꾸지 않는다. 비교버튼은 같은 설정의 A/B를 직렬 실행해 각각 결과/오류/시간을 보존한다. 비교 전체는 두 질의이며 각 질의의 0/1 생성 제한과 구분한다. 요청별 corpus/구현/모델/프롬프트 hash·실행 순서·run ID를 JSON으로 내려받는다.

기존 root UI는8000, 후보는8001을 기본으로 하되 이미 사용 중인 포트를 빼앗지 않는다. 현재 API 경로는 `/api/ask`다. 기존 status/error HTTP 상태·same-origin·body 제한·loopback·server lock을 유지한다. 비교 UI는 기존 결과를 새 실행으로 표시하지 않는다. 원문15청크 기본값을 유지하며 source-v2는 명시된 별도 선택/CLI로 검증한다. source-v2 UI 선택을 추가한다면 서버 allowlist를 사용한다.

실제 브라우저에서 정상·복수 근거·근거 없음·한쪽 오류·비교중 입력·좁은 화면·JSON 저장을 확인한다. 모델을 이용한 CLI/API smoke와 기존107개 단계/19개 루트 회귀(착수 시 실제 목록 확인), 신규 계약 비교/후보 회귀·독립 복사 실행을 수행한다. 테스트 수를 맞추려고 기존 검사를 빼지 않는다. 기존 하네스12개도 큐/채택이 유지되는지 확인한다.

## 결과 파일과 후속 기반

`docs/verification/p011/`에 protocol/rubric, preservation-manifest, environment, parity, 원응답/trace, quality-review, latency/resource-report, browser-check, copy-regression, final-review와 `adoption-decision.json`을 저장한다. 판정 파일에는 decision, protocol/hash, 기준/후보 commit·파일 hash, 각 gate PASS/FAIL/미확정, 의미 지표, 비용·한계, selected_implementation/source_path, evidence 경로를 포함한다. 실제 실행 전에는 이 파일을 통과 결과로 만들지 않는다.

- ADOPT_LANGCHAIN: 모든 계약/품질/안정성 gate 통과, 실제 속도/비용 보고 완료. 다음 P010은 후보의 LangChain 경로를 복사·선별할 수 있다.
- KEEP_DIRECT: 관찰된 품질 저하로 후보와 실패 증거를 보존하고 다음 P010의 기본은 기존 직접 구현이다. 미해결 계약/안정성 실패가 있으면 역시 직접 구현을 유지하지만 P011의 해당 C2/C5는 FAIL이며 수정/재검증 또는 plan 범위 재검토 전 완료 처리하지 않는다.
- INCONCLUSIVE: 유효한 비교는 수행했으나 의미 판정이 불확실. 기존 직접 구현을 유지하고 P010 준비 검토에서 재실험 필요성·선행 범위를 정한다. 미구현/미실행을 완료로 분류하지 않는다.

P010 준비 검토가 이 판정과 복사 대상 hash를 확인한 뒤 상세 계약을 확정한다. P011 완료가 자동 LangChain 채택이나 P010 준비 완료를 뜻하지 않는다. 선택된 기반으로 Hybrid를 진행한 후 P007/P008 청킹 실습을 수행한다.

## 의존성 선택 근거

[LangChain Core 배포 정보](https://pypi.org/project/langchain-core/1.7.0/)에서 1.7.0·Python>=3.10,<4·MIT를 확인했다. 해당 wheel SHA256은 `e82b24d7ac51fc74874baa29d6b3c0b8234880d4f3d897f8ff57fb80dfd9b07d`이며 설치 때 다시 검증한다. `langchain-core`는 provider 독립 추상화를 제공한다. [공식 Runnable reference](https://reference.langchain.com/python/langchain-core/runnables)는 함수의 Runnable 변환과 단계 조합 인터페이스를 제공한다. 선택은 기존 경계를 유지하기 위한 프로젝트 설계 결정이며 성능 개선 보장은 아니다. provider 통합 패키지나 LangGraph를 이 과제에 포함하지 않는다.
