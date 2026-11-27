# P026 준비 검토 — 2026-11-27

READY. P025 완료 SHA d7406e2b6e2c611cc741ad823d59a90bcefd6043가 dev/personal-dev에 일치하며 공개 API validate_config/preview/invoke와 실제 transport 코드/증거를 읽었다. 이전 goal turn은 세 provider 구현·offline 검증·전달을 완료한 progress다.

기존 P007 source_io/experiment_common은 synthetic/source-v4 고정이고 Naive rag는 Qwen lock을 전제한다. 이를 풀면 기존 실험 재현 계약을 깨므로 새 일반 문서 모듈에서 순수 알고리즘만 선별 재사용하고 provenance를 남긴다. P025 실제 API에 연결하되 기존 runner는 보존한다. 이것은 전체 목표를 축소한 것이 아니라 공개 모델/API 교체를 문서 기반 RAG로 연결하는 독립 증분이다. Dense/Hybrid/리랭커/UI/실제 Drive/실모델 검증이 남으면 전체 완료가 아니다.

경로·CLI·일반 문서 schema·version/hash·NFC/page provenance·규칙 청킹/최대길이·BM25·문맥 예산·JSON/citation·비교·실패·지원 상태를 상세 계약에 고정했다. PDF는 현재 설치된 pypdf6.21.2로 테스트하며 모델/패키지 다운로드가 필요 없다. 개인 문서/외부 계정/유료 호출은 이번 검증에 필요 없다. ask/compare가 실제 provider에 연결되는 코드까지 구현하고 시험만 fake transport로 분리한다.

P013 hold와 기존 평가 선행은 유지한다. P026에서 Faithfulness/Correctness/검색 지표를 계산한 것처럼 표시하지 않는다. P013 미완료가 독립 parsing/search/provider 연결의 구현을 막지는 않는다. 스캔/빈페이지는 review 상태로 명시하고 조용히 누락하지 않는다. credential/원문 private artifact를 공개 Git에 넣지 않는다.

사용자 goal과 같은 프로젝트 준비 검토·dev 직접 등록 위임에 따라 기존 dev에 정확 SHA·문서·실행 범위를 전송한다. 실모델 보류를 재개하지 않는다. P026 C1~C3 검증, 기존 기록 불변, normal personal/dev push를 관찰하며 main 승격은 제외다. 기존 미커밋 네 계획 파일은 별도로 보존한다.
