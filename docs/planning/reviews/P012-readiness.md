# P012 준비 검토 — 기본 학습과 구현 비교 실험 분리

검토일: 2026-10-29 Asia/Seoul. 상태: 준비 완료, 제품 구현/검증 미실행.

사용자가 plan 채팅에서 LangChain 기본값·별도 비교 실험 메뉴 계획과 dev 전달을 명시했다. 기존 완료 계약 변경이므로 P011을 고치지 않고 다음 미사용 P012를 만들었다. plan 직접 요청이므로 가상의 dev 접수 ID는 만들지 않는다. 접수 대기0건, plan/dev clean, dev 채팅 idle, 커밋 `150884f5576aa75cdb324f66ff0a26e4fdf97d2b` 및 personal/dev 일치를 확인했다.

P011 완료 카드·adoption-decision.json·final-review.md를 확인했다. 판정 ADOPT_LANGCHAIN, gates PASS, 미해결 차단 없음이다. 고정20질문의 각3회 반복 비교 결과이며 일반 품질 동등성·속도 향상은 입증하지 않는다. P011의 Direct UI 기본값 보존은 당시 계약이었다. 새 사용자 요청으로 후보의 기본 실행 진입만 바꾸고 P011 문서/실패/판정은 그대로 둔다.

실제 코드는 후보 `scripts/serve_compare.py`가 web_compare를8001에서 서빙하고 `/api/ask` 생략값direct, `/api/compare` 명시 direct→langchain 루프와 공통 잠금을 사용한다. `ask_compare.py`와 `comparison.ask`도 기본direct다. 보존된 `ask.py`/`serve.py`는 직접 구현 사본이다. web_compare/index.html에 구현 선택과 비교 버튼이 기본 폼에 있고 app.js는 구현 선택 DOM과 고정 Direct 안내에 결합돼 있다. 별도 경로의 DOM에서 없는 요소 접근으로 오류가 나지 않도록 두 화면 동작을 실제 브라우저에서 확인하도록 계약화했다.

설계 결정: 후보8001 `/`는 LangChain 학습, `/experiments/implementation`은 기존 비교 도구다. 기존8000과 보존 Direct CLI를 바꾸지 않는다. API/CLI/dispatcher 생략값은 일관되게 LangChain이며 명시 direct와 비교 순서는 호환 유지한다. UI 이동과 기본값만 바꾸므로 파이프라인/모델/문서/검색 계약을 그대로 두고 의미 변경 여부와 대표 실제 질의로 검증한다. P011의120슬롯 비교를 다시 요구하지 않는다. 최대16회 실제 생성과 관련 전체 회귀·독립복사·브라우저/JSON을 완료 기준으로 정했다.

P012 선행P011, 우선순위66으로 dev 다음 작업에 등록한다. P010 초안의 선행은 P012로 변경하고 P011 판정 검토 요구는 유지한다. 작업 전환 순서는 P012 완료 → 별도 공개 설치형 하네스 → 이후 HR RAG Hybrid다. 하네스 제품 자체의 설치 파일/문서/코드는 이 HR RAG 계획에 넣지 않는다. 현재 roadmap에는 전환 순서만 기록한다.

기획 검증은 카드 파싱·기존 완료 상태 유지·dev 다음 P012·P010 초안/선행·로컬 링크·diff 공백 확인이다. plan의 guard SKIP은 dev PASS가 아니다. dev는 정확한 준비 커밋을 통합·채택한 후 구현한다. 사용자 명시 전달 지시로 기존 dev 채팅에 이 범위를 전송한다.
