# P012 LangChain 기본 학습과 구현 비교 실험 계약

## 변경 경계

[P012](../planning/plans/P012.md)의 계약이다. 기준 dev `150884f5576aa75cdb324f66ff0a26e4fdf97d2b`의 P011 판정은 ADOPT_LANGCHAIN이다. P011에서 검증한 동일 검색/문맥/생성 파이프라인을 유지하고 진입 화면·기본 라우팅만 변경한다. P011 카드·비교 계약·protocol/rubric·판정/실패/성능 증거와 후보의 판정 사본을 소급 수정하지 않는다. 당시 `ui_default=direct`는 P011 시점 기록이다. 현재 설정은 새 P012 안내/설정에서 설명한다.

변경 대상은 후보 `scripts/serve_compare.py`, `scripts/ask_compare.py`, `scripts/comparison.py`, `web_compare/`, 후보 안내·현재 manifest와 관련 신규/수정 테스트다. 필요하면 같은 후보 내부에 화면 파일을 추가한다. 원래 `1. Naive RAG/` 제품 코드/데이터/lock/web/tests와 후보의 원본 Direct 사본·`rag_langchain.py`·검색/generation/인용 경계·모델/프롬프트·색인·환경 pin은 보존한다. 원래 단계 README/LEARNING_GUIDE/stage-manifest는 기본 학습 진입·실험 링크·현재 출처 안내만 갱신 가능하며 원본 hash를 기록한다. 무관한 리팩터링은 하지 않는다.

## 화면과 경로

| 진입 | 동작 |
| --- | --- |
| 후보 서버 `http://127.0.0.1:8001/` | 기본 학습: LangChain 단일 실행, 질문/검색기/top-k/문맥 예산, 검색 후보·전달/제외 문맥·답변/인용·trace·JSON 유지 |
| 상단 “실험” → “구현 비교” | `/experiments/implementation`로 이동. 직접 URL·새로고침·뒤로/앞으로 동작하며 “학습으로 돌아가기” 제공 |
| `/experiments/implementation` | Direct/LangChain 명시 선택 단일 실행 + 두 구현 비교 + 기존 결과 상세/한쪽 오류/비교 JSON 유지 |
| 기존 직접 구현 서버8000 | 기준선으로 보존. 현재 학습 시작점은8001이라고 문서에서 구분 |

기본 화면에는 구현 선택기와 두 구현 비교 버튼/비교 결과 영역을 노출하지 않는다. 단순히 비교 패널을 접어 기본 폼에 남기는 방식은 별도 메뉴 분리로 보지 않는다. “LangChain” 사용 사실은 짧게 표시하고, 실험 메뉴에는 구현 구조의 비교이며 수동 한 쌍이 정식 품질/속도 검증을 대체하지 않는다고 안내한다. 학습 화면의 BM25↔Dense는 구현 비교와 다른 조작이므로 유지한다. 기본 corpus15·K5·문맥8000문자·입력 제한은 그대로다. 새 corpus 선택·Hybrid·청킹 실험은 추가하지 않는다.

네비게이션은 의미 있는 링크/버튼·키보드 접근·현재 위치 표시를 갖춘다. 두 화면 모두390px 및 데스크톱에서 조작과 결과를 읽을 수 있어야 한다. 새로고침은 자동 질의/비교를 실행하지 않는다. localStorage/URL/실험의 이전 Direct 선택 때문에 기본 화면이 Direct로 바뀌어서는 안 된다.

현재 문서의 실행중에는 제출·비교·입력 변경을 잠그고 해제한다. 앱 메뉴 이동도 완료 전 막거나 명확히 안내해 중복 요청을 유발하지 않는다. 브라우저 자체 이동/닫기는 서버 생성 취소를 보장하지 않으며 서버 공통 잠금을 유지한다. 돌아온 화면이 이전 응답을 새 실행으로 표시하지 않도록 결과·다운로드 상태를 격리한다. 새 요청 시작 시 이전 결과/다운로드를 초기화하고 실패 후 조작이 복구된다.

## 기본값과 API/CLI 호환성

| 경계 | implementation 생략 | 명시적 선택 |
| --- | --- | --- |
| 기본 학습 폼 | LangChain을 명시해서 `/api/ask` 호출 | 폼에서 Direct 선택 없음 |
| 후보 `POST /api/ask` | `langchain` | `direct`/`langchain` 지원; null·빈 문자열·기타 값은400 |
| 후보 `scripts/ask_compare.py` | `langchain` | 기존 `--implementation direct|langchain` 지원, 잘못된 값은 입력 오류/exit2 |
| 후보 `scripts/comparison.py:ask` | `langchain` | 유효하지 않으면 기존 input 오류, fallback 없음 |
| 후보 `POST /api/compare` | 기본값 변경과 무관하게 명시적 direct→langchain | 기존 입력 검증·직렬 두 결과·pair ID/설정/순서 유지 |
| 보존된 `scripts/ask.py`, `rag.ask`, `serve.py` | 기존 Direct | 기준선 전용으로 문서에서 명시 |

새 alias CLI가 필요하지 않다. 기본 사용 예시는 기존 `ask_compare.py`의 implementation 생략으로 통일하고 파일명이 compare여도 기본 실행은 한 번임을 설명한다. `serve_compare.py` 시작 명령/포트8001은 유지한다. loopback·same-origin/CSP·body/질문/K/예산 제한·HTTP 상태400/502/504/500·하나의 서버 pipeline lock을 보존한다.

각 질의는 no_context0회/일반 최대1회 생성한다. 비교는 두 독립 질의이며 합계 최대2회다. LangChain 실패 시 Direct 자동 fallback/retry를 추가하지 않는다. trace 구현 식별자·JSON의 결과/설정·run ID는 실제 실행과 일치한다. `/api/decision`은 역사적 P011 판정을 그대로 제공해도 되지만 현재 기본값을 Direct라고 안내하는 문구는 제거한다. 현재 기본값 표시와 과거 판정 기록을 별도로 다룬다.

## 검증 범위와 증거

1. 변경 전 파일 inventory/hash와 기준 커밋, P011 판정 hash를 기록한다. 완료 후 원본·후보 Direct 사본·파이프라인·데이터/lock·P011 증거의 불변을 확인한다. 후보 copy-manifest의 최초 출처/hash를 지우지 않고 현재 변경 파일·hash·P012 이유를 기록한다. 과거 후보 source commit은 과거 증거에서 고치지 않는다.
2. 자동 검사: 생략→LangChain, 명시 Direct→Direct, 잘못된 값, 무문맥0회, 생성 최대1회, 비교의 명시 순서/최대2회, 한쪽 오류 보존, HTTP 입력/보안 경계, 동시 요청 서버 잠금, 경로 직접 접근/404를 독립 기대값으로 검사한다. 현재 기본값 변경을 요구하던 테스트만 P012 근거로 갱신하고 나머지 회귀를 제거하지 않는다.
3. 실제 모델 CLI/API: 생략한 후보 CLI와 API가 LangChain trace를 반환, 명시 Direct 가능, 기본 UI 정상 질문·복수 근거·근거 없는 질문, 실험 A/B 결과를 관찰한다. 원문/인용·전달 근거를 확인하되 기존 부분 답변을 새 품질 성공으로 포장하지 않는다. 모델 payload/검색 의미가 바뀌면 이번 UI 계약 안의 구현을 수정하고 재검증한다.
4. 실제 브라우저: 기본/실험 화면 데스크톱과390px, 메뉴·직접 URL·새로고침·뒤로가기, Direct 선택 후 기본으로 복귀 시 LangChain, 실행중 입력/메뉴 처리·실패 복구·현재 결과 JSON 및 A/B JSON 저장을 확인한다. 오류/지연 fixture는 실제 모델 검증과 명확히 구분해 증거를 남긴다. 정상 실험 후 기본 화면에 비교 결과가 잔류하지 않아야 한다.
5. 기존 단계107·후보 기존107+P011 추가32·루트19·하네스12와 P012 추가/변경 검사를 실행한다. 실제 발견 수/내용을 기록하고 테스트 수를 맞추기 위해 삭제하지 않는다. 후보만 별도 임시 위치로 복사한 뒤 부모 import 없이 새 경로·기본 CLI/API를 확인하고 최소 대표 실제 질의1회로 독립 실행을 확인한다. 기존 절차의 고정 로컬 모델 재사용을 명시하고 색인은 잠금 없는 snapshot/export 절차로 준비한다.
6. 실제 생성은 이번 변경 검증에 최대16 dispatch(오류 포함)로 제한하고 ledger에 용도·횟수·상태를 기록한다. mock은 별도 집계한다. P011 대규모 반복 비교를 재실행하거나 새 모델/패키지·유료 API를 도입하지 않는다. 수정 재검증이 상한을 넘길 경우 근거를 plan에 올린다.

`docs/verification/p012/`에 preservation, routing/API/CLI, browser-check(스크린샷/다운로드 확인), regression, copy-smoke, dispatch ledger, final-review를 남긴다. 증거 파일명은 개발자가 명확한 이름으로 정할 수 있다. final-review는 변경 파일/현재 실행법/구현 commit/hash·P011 보존·테스트/제한·사용자 작업 순서(P012 후 설치형 하네스)를 연결한다. dev는 정확한 plan SHA 채택·guard·queue·커밋된 최신 PASS를 확인하고 정상 dev push 후 결과를 보고한다. P010은 자동 진행하지 않는다.
