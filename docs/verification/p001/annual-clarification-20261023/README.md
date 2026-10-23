# P001 합성 문구 정정 — 2026-10-23

사용자의 명시 요청에 따라 annual-carry의 이월 한도(5일분)와 기한(다음 해 3월 31일)을 분리하여 명확하게 표현했다. 가상 규정이며 정책 의미 변경은 없다.

- PASS: 15개 청크 중 annual-carry text만 변경. ID·출처·version 등 metadata 및 질문/정답 라벨은 동일하다. corpus 변경은 SHA-256으로 식별하는 기존 규칙을 따른다.
- 이전 corpus SHA-256: 53d262cb4d11ba73bd08dd559676d6df002fb46ef15afa5f94e01508620abedc
- 현재 corpus SHA-256: 2c8edcd64eef14f68512fb4d232d2267528e9bc63d161f37d8ac7dfcc198802f
- PASS: 고정 BGE-M3로 15개 청크 재색인·재open 검증 후 로컬 index-v1에 적용. 이전 색인은 .runtime/index-before-annual-clarification-20261023에 보관했다.
- PASS: 실행 중인 127.0.0.1:8000/api/ask에 q06, Dense, top-k 5, 문맥 8000자로 실제 호출. annual-carry 검색 1위, 새 원문 문맥 전달 및 정확한 인용, 최대 5일분/다음 해 3월 31일 답변 확인. 원본 응답은 live-result.json 참조.
- PASS: contract_guard check. 기존 P카드·기존 검증 결과와 stage-manifest의 최초 복사 hash는 역사적 기록으로 보존한다. 과거 성능 수치는 수정 전 corpus의 결과다.
