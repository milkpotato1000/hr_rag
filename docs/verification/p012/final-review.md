# P012 완료 — LangChain 기본 학습과 별도 구현 비교

검토 시각: 2026-10-29T11:31:15+09:00. 검토 주체: Codex. **PASS**, 미해결 차단 없음.

기본 화면에서 구현 선택에 신경 쓰지 않고 RAG 검색·문맥·답변을 관찰할 수 있도록 LangChain 단일 실행으로 바꿨다. Direct/LangChain 선택과 A/B는 상단 **실험 → 구현 비교**로 옮겼다. 검색 방식·top-k·문맥 예산과 검색/인용/trace/결과 JSON은 기본 화면에 유지한다.

## 현재 진입과 실행

| 진입 | 현재 동작 |
|---|---|
| http://127.0.0.1:8001/ | LangChain 기본 학습 |
| http://127.0.0.1:8001/experiments/implementation | 명시 구현 단일 실행 및 Direct→LangChain A/B 실험 |
| http://127.0.0.1:8000/ | 보존된 원래 Direct 기준선 |
| 후보 ask_compare.py / comparison.ask / POST /api/ask | implementation 생략 시 LangChain; 명시 direct 지원 |
| 보존 ask.py / rag.ask / serve.py | Direct 기준선 그대로 |

후보 폴더 `1. Naive RAG/variants/langchain/`에서 `.venv/bin/python scripts/serve_compare.py --port 8001`로 실행한다. 단일 CLI 예시는 `.venv/bin/python scripts/ask_compare.py --question '생일 휴가의 자격과 신청 기한, 사용 기간을 함께 알려 주세요.'`다. 파일명이 compare여도 기본 CLI는 단일 질의다. null/빈 문자열/알 수 없는 구현은 입력 오류이며 fallback하지 않는다.

## 구현과 보존

정확한 plan `0064b8e43a016d498bf3861bf04b46ee3ff686af`를 통합·채택했다. 기준 dev는 `150884f5576aa75cdb324f66ff0a26e4fdf97d2b`, 구현 커밋은 `307a7e7c5b4a356d350e811c15e7649fa85546e3`다. 변경 대상은 후보 dispatcher/CLI/server wrapper, web_compare의 학습·실험 문서와 공통 JS/CSS, 관련 테스트와 현재 안내/manifest다.

DEFAULT_IMPLEMENTATION을 LangChain으로 통일하고 기본 폼도 명시 LangChain 요청을 전송한다. 두 화면은 서로 다른 HTML이며 기본 문서에는 구현 선택기/비교 버튼/비교 결과 DOM이 없다. 공통 JS는 실험에만 있는 DOM을 조건부로 접근한다. 실행 중 입력과 앱 메뉴를 잠그고 메뉴 클릭 시 대기 안내를 보여준다. 새 요청은 이전 결과와 다운로드 상태를 지운다. 브라우저 history 복귀 문서도 이전 결과를 새 실행처럼 표시하지 않으며 새로고침은 자동 생성하지 않는다. 브라우저 자체 닫기/이동은 서버 생성 취소를 보장하지 않으며 서버 공통 잠금은 유지한다.

원본/후보 Direct 사본, rag_langchain.py, 검색·생성·인용 경계, 데이터·모델·프롬프트·환경 lock, P011 증거와 판정 사본은 보존했다. 471개 기존 파일 inventory에서 허용한 wrapper/UI/안내 변화만 확인했다. 원본 단계 README/가이드/manifest는 현재 진입 안내만 변경했다. 원본·후보·독립 복사본의 두 색인은 P011 논리 hash와 동일했다. P011 판정 안의 ui_default=direct는 당시 기록으로 그대로 두고 현재 기본값은 P012 learning_entry에 기록했다.

- 현재 copy-manifest SHA256: `9466634fe0de49f9985caf2379bdda6f9983ac03ea8f5fea6231e0d30a73b902`.
- 보존 파이프라인 SHA256: `273698d2f34bd4017722a9fbc92d77032b2352b44936c49a158213e1c367303c`.
- 현재 dispatcher SHA256: `cd76fa3dbac82635c1895e206ec599a25f0e89d9a2199b28164692b0d632135c`.
- 최초 출처/copy hash는 지우지 않고 P012 변경 사유·현재 hash·이전 hash를 manifest에 연결했다.

## 검증 결과

| 검증 | 결과 | 증거 |
|---|---|---|
| 원본 단계107 / 후보 기존107 | PASS | baseline-tests.log / candidate-tests.log |
| P011 후보 추가32 | PASS; 생략값 기대1곳만 P012 근거로 변경 | langchain-tests.log |
| P012 추가11 | PASS; 기본/명시/잘못된 입력·CLI exit2·생성0/1·경로404·보안/상태·비교/단일 공통 잠금 | learning-tests.log |
| 루트19 / 하네스12 | PASS | root-tests.log / harness-tests.log |
| 실제 CLI/API 및 독립 복사 | PASS | routing-smoke.json / copy-smoke.json |
| 실제 학습 정상·복수근거·보류 및 실험 A/B | PASS | browser-*.json / live-check.json |
| 메뉴/키보드/Direct 후 복귀/뒤로·앞으로·새로고침 | PASS; 자동 질의·이전 결과 잔류 없음 | browser-check.json / *.ax.txt |
| 실행중 잠금·오류 복구·한쪽 실패 보존·JSON | PASS; 오류는 명시 fixture | fixture-error.json / fixture-pair-error.json |
| 390px와1200px 학습/실험 | PASS; 실제 iframe 조작·스크린샷 확인 | narrow-*.png / desktop-*.png |
| 파일/모델 payload/원문/색인 보존 | PASS | preservation.json / live-check.json |

전체 자동 회귀는288개다. 새로운 패키지/모델은 도입하지 않았다. 독립 복사본은 새 가상환경에 기존 hash lock과 로컬 wheel로 설치했고 원본 모델 서비스를 명시적으로 공유했다. 새 경로의 기본 CLI 실제 질의와 기본 API 무문맥0회 실행을 확인했다. 실행 파일은 부모를 import하지 않으며 최종 출처 manifest만 smoke 이후 동기화했다.

실제 생성은 **9회/상한16회**다: 원래 후보 CLI 생략/Direct 각1, 독립 복사 CLI1, API 생략1, 기본 UI 정상/복수근거/보류 각1, 실험 A/B2. 복사 API 무문맥은0회다. UI 지연/오류/layout fixture는 모델0회로 별도 ledger에 기록했다. 자동 retry는 없다.

9개 실제 응답의 구현 식별자, 검색/문맥, 실제 generation request, 인용 원문 bytes, 검토된 P011 출력 일치를 확인했다. 생일 종합의 연1일 본문 누락도 그대로 남는다. 이 변경을 품질 개선이나 속도 개선으로 주장하지 않는다. P011의120슬롯 대규모 비교는 반복하지 않았다. 검증 도구의 UTF-8 입력 오류, summary locator 차이, 다운로드 도구의 긴 응답 공백은 notes.md에 보존했고 검사를 제외하지 않았다.

## 완료와 후속

현재 학습 기본값과 과거 P011 판정은 분리해서 기록했다. 구현·실제 검증·독립 복사·보존·정확한 채택이 모두 통과했다. 커밋 훅과 최종 queue/guard 결과는 final-checks.txt에서 확인한다.

사용자 작업 순서는 **P012 완료 → 별도 공개 설치형 plan-dev 하네스 제작 → 이후 HR RAG Hybrid → 청킹 비교 실습**이다. 하네스는 별도 프로젝트에서 준비하며 이 dev 작업에서 다른 저장소 생성/게시나 P010을 자동 착수하지 않는다.
