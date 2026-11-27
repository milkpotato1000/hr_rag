# P025 준비 검토 — 2026-11-27

READY. P024 완료 7573c934c76aef493abb6dd1648393c025288d9c를 dev/personal-dev에서 확인했다. 이전 goal turn은 P024 문서/검증/전달을 실제 완료한 progress이며 이번에는 실제 provider 구현으로 진전한다.

Graphify AST로 generation/rag/runtime_common/evaluator 네 파일을 임시 캐시에서 구조 검사했다(71 nodes,177 edges, semantic LLM 호출0). 기존 graph는 없었으며 전체 저장소 그래프 구축을 수행하지 않았다. 실제 소스를 함께 읽어 hard-coded 모델·lock·LocalAPI와 Generator 경계를 확인했다. P013 불변 계약과 강결합이 있어 새 모듈을 루트 rag_package/llm에 만들고 현재 실행 경로에는 후속 통합으로 연결한다. 기존 기준선을 바꾸지 않는 것이 비교 가능성과 중지 보존에 필요하다.

표준 라이브러리 독립 경계, Ollama/OpenAI Chat/Claude Messages wire 매핑, strict 설정/결과·비밀값 정책, fake transport와 실제 HTTP 경계 검증, 제품 문서/예제 위치·완료 조건이 명확하다. 공식 API 문서를 실제 확인해 최신 Anthropic version/auth와 OpenAI 출력 토큰 필드 차이를 계약에 적었다. 실제 provider가 지원하지 않는 모델 옵션/문법은 오류로 보고하며 포괄 호환성을 주장하지 않는다.

실모델 메모리·다운로드·P013 grant·상용 API 비용·개인 문서 전송은 이번 범위에 없다. 따라서 사용자의 기존 중지나 신규 비용 결정을 필요로 하지 않는 독립 개발 작업이다. 실제 HTTP 호출 가능한 코드를 구현하되 이번 검증의 모델 실행/과금은0회다. live 성공은 주장하지 않는다. 기본 HF 모델/선택 API 방향, 나중 RAG 통합과 최종 패키지 목표는 그대로 유지한다.

P025 C1~C3는 계약의 전체 검증 행렬과 지원 상태/증거를 포함한다. exact adoption·실패 보존·정상 personal/dev push를 따른다. 준비/인계 권한은 현재 goal과 같은 프로젝트 AGENTS 위임, 기존 dev만 대상으로 한다. 네 기존 미커밋 계획 파일은 보존하며 이번 SHA에 포함하지 않는다.
