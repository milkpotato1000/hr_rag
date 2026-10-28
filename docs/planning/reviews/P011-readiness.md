# P011 준비 검토 — LangChain Naive 비교

검토일: 2026-10-28 Asia/Seoul
상태: 준비 완료 · 구현/품질 유지/채택 판정은 미실행

## 요청·중복·기준 확인

사용자는 dev 채팅에서 현재 Naive를 LangChain 기반으로 리팩터링하되 기존 구현을 비교용으로 보존하고 검색 결과·답변 품질·속도를 비교한 뒤 품질 저하가 없으면 이후 로드맵의 기반으로 이어가도록 plan에 요청하라고 명시했다. dev 채팅 `01a1618d-8c93-7122-9902-7c839eed66a1`의 전달 메시지를 수신했다. 이 검토는 plan의 요구·계약 작성과 준비 등록이며 dev 제품 구현을 수행하지 않는다.

기존 P001~P010을 조회했으며 같은 LangChain 비교 카드는 없었다. P010은 Hybrid 검색 변경이므로 그대로 두고 다음 미사용 번호 P011을 부여했다. plan 기준은 e830ee037029714d88686c84d8a5d761416393b9, dev 기준은 58e8eb793b95c524c256c0206e37aa15ff99c6ff다. 두 작업 트리의 초기 clean 상태와 dev guard PASS를 확인했다. P001~P006/P009 완료, P010/P007/P008 초안을 확인했고 P011 선행을 P009, P010 선행을 P011로 조정했다.

이번 요청은 plan에 직접 전달된 사용자 명시 범위로 검토한다. 검토 시점 dev에는 구조화 `docs/feedback/dev/requests/` 기록이 아직 없으므로 가상의 요청 ID/hash나 검토 결정 파일을 만들지 않았다. 요청 원문·전달 출처는 P011에 보존한다. 이후 dev에 실제 접수 기록이 커밋되면 같은 P011로 연결하고 중복 카드/승격을 만들지 않는다. plan이 대신 dev 파일을 작성하지 않는다.

## 실제 인터페이스 조사

- `scripts/rag.py`: retrieve/select_context/context_snapshot/validate_answer/ask로 경계가 나뉨. 전체 청크 JSON 문자 예산, 불변 snapshot, no_context 분기, request trace와 인용 검증이 있음.
- `scripts/generation.py`: 요청마다 schema를 deepcopy해 허용 ID enum을 주입하고 동일 messages + `/api/chat` model/options를 전송함. 전후 모델 metadata/digest 검사와 hidden thinking 거부가 있음. 이 경계를 Runnable 어댑터로 재사용하면 메시지 직렬화 변경을 피할 수 있음.
- `scripts/runtime_common.py`: STAGE는 해당 파일의 부모 단계 경로, Python3.12.14/Ollama0.40.8·numeric loopback·고정 BGE digest와 Qwen lock을 사용. 후보를 독립 복사하되 원래 runtime을 덮어쓰지 않는 준비가 필요함.
- `scripts/serve.py`: 실제 POST 경로는 `/api/ask`; ThreadingHTTPServer/실행 lock·same-origin/body/입력 제한을 사용. 이전 일부 대화의 `/api/chat` 표현은 모델 서버 경로와 혼동되므로 후보 API는 `/api/ask`를 유지함.
- `scripts/ask.py`: chunks/index를 명시할 수 있어 source-v2를 별도로 평가 가능. UI 기본 corpus는15개이며 PDF 회귀20청크와 섞지 않음.
- `generation-lock.json`, `runtime-lock.json`, `requirements.lock`, synthetic 원문/질문, P009 final-review와 실제 학습 가이드를 읽음. q03/q07 조건 누락, q08 과도 보류, q09 인용 지지 미충족은 남은 의미 품질이며 구조 검증 통과와 구분해야 함.

## 설계·판정 결정

1. 같은 Naive 구현 비교이므로 원래 stage를 보존하고 내부 `variants/langchain/`에 독립 사본을 둔다. 새 번호 단계로 만들지 않는다. candidate direct 경로는 원본 사본을 유지하고 root baseline과 동등성부터 확인한다.
2. 최소 `langchain-core==1.7.0`의 단계 조합을 선택한다. 전체 ask를 단일 wrapper로 감싸는 것은 부족하다. 기본 검색/provider 통합으로 교체하지 않아 BM25·Dense·요청 payload 변화와 리팩터링 효과를 분리한다. 원래 dependency pin과 충돌하면 plan 재검토한다.
3. PyPI의 해당 공식 배포 정보에서 Python 범위·MIT·wheel hash를 확인했다. 공식 Runnable reference는 검색으로 API 설명을 확인했지만 페이지 직접 열기는 markdown content-type 오류였으며 설치 호환성/실행 PASS를 주장하지 않는다. 실제 설치·import·pin resolution·배포 hash 검증은 dev의 C1이다.
4. 고정20case ×3회 ×A/B, 별도18 cold 슬롯, 사전 protocol/rubric 커밋과 원문 기반 의미 평가를 계약화했다. 기존14는 이미 본 자료이고 새4개도 작은 확인 세트이며 일반 동등성을 보장하지 않는다.
5. 품질 기준은 case별 필수 사실·완전 정답·주장 인용 지지·보류·오류/허구의 비열화 관찰이다. 숫자/순위/payload 동등성과 모델 응답 의미 변동을 분리한다. 사후 임계값 완화·좋은 실행 선택을 금지한다.
6. 속도는 cold/warm/모델 로드 교체·실행 순서·반복·계층별 시간을 분리한다. 기존 runtime의 모델1개 로드 제한을 고려해 Dense의 “warm”을 모든 모델 상주로 오해하지 않게 했다. 속도/메모리/의존성 비용을 품질과 따로 공개한다.
7. ADOPT_LANGCHAIN/KEEP_DIRECT/INCONCLUSIVE를 구분한다. 품질 유지 결과를 미리 승인하지 않는다. P010은 커밋된 결과를 읽고 선택된 구현 commit/path/hash를 확정한 뒤 준비 완료로 전환한다. 미구현/미측정은 INCONCLUSIVE 완료로 처리하지 않는다.

## 준비 완료 범위

이전 로컬 모델/loopback 자원과 후보 격리 의존성 설치, 제한된 실제 모델 비교, 기존 UI 보존과 후보 UI 검증으로 수행할 수 있다. 실제 HR/Drive 계정·외부 메시지·유료 자원·새 모델·배포는 포함하지 않는다. 본문에 확정한 기술 선택은 사용자 요청을 실행 가능하게 하는 계획 판단이며 추가 업무 결정은 없다.

P011 카드와 비교 계약, 현재 로드맵/프로젝트 기획/단계 규칙/P010/P007/P008 선행 설명을 함께 갱신한다. 완료된 P001~P006/P009 요구·체크·로그와 dev 제품·증거는 변경하지 않는다. plan의 기존 준비 검토/등록 위임으로 P011을 준비 완료로 등록한다. dev는 커밋된 이 계획을 정확히 adopt한 후 구현한다.

## 기획 검증

작업 큐에서 dev 다음 P011, plan 다음 P010, P007의 P006/P010 및 P008의 P007 의존 관계와 기존 완료 진척을 확인한다. 로컬 문서 링크·완료 조건/실행 상태 파싱·diff 공백을 검사한다. plan guard의 SKIP을 dev 검증 PASS로 보고하지 않는다. 제품 코드·설치·모델 평가·브라우저 검증은 아직 실행하지 않았다.
