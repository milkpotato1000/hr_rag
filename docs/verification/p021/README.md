# P021 검토본 개정 — 구현 완료, 실제 UI 검증 미완료

2026-11-04. 계획 `3a8c23e39df1b8102420a7dba5577fae56b56d2f`를
`6e5d437`에서 정확히 통합·채택했다. 이번 작업은 run001을 변경하지 않는 오프라인
검토본 개정이며 새 모델 호출·다운로드·서버 변경은0회다. 사람 승인은 모두 null이다.

## 결과

- `evaluation/project_b/preparation/artifacts/run002/review.html`: 질문10개 → 주장45개 → 각 근거 원문. 인용은 기본 펼침, 상세69개는 기본 접힘. 질문 탐색과 이전 보고서 링크 제공.
- `packet.json`: 중복 제거를 실제 JSON에 반영. gt01-c01/c03→c02, gt05-c01→c02. gt04-c01의 반복 금액만 제거하고 c02의1만 원 유지. 나머지 주장 및 판정18개 동일.
- `revision-mapping.json`: 기존48개 각각의 문장/ID/답변 위치/원문 근거와 새45개 대응·사유. 기존 ID는 재번호하지 않음.
- `packet-manifest.json`: 패킷/HTML/매핑 파일 hash. 새 패킷은 부모 패킷 hash·실행 이력 경로·부모 파일 hash를 포함한다.
- gt09/10: 금액 미명시 확인 필요, 주장/가짜 인용0개, 전체 원문·정책 목록/대조 기록 링크.

새 패킷 SHA: `e6a264387d3dd169168bcf1733156bf91bd4bdf76fc8bb70f5a704e3bc7a2b0e`.
정확한 JSON/HTML 파일 SHA는 이 폴더의 `delivery.json`에 기록한다.

## 검증

`unit-tests.log`: 기존17개와 새7개, 총24개 PASS. 지정 문구와45개 ID, 조건/예외·금액,
변경하지 않은 주장/판정, 원문 slice·Unicode 답변 위치·페이지·해시, 미승인, 부재 후보,
HTML escaping/내장 JSON, 63개 펼친 인용/69개 기본 접힌 상세 및 상대 링크를 검사했다.
검증은 모델을 호출하지 않으며 오프라인 테스트에서는 소켓 생성도 차단했다.
실행 CLI는 run002에 대한 모델 실행을 거부하는 것을 확인했다.

`offline-replay.json`: 임시 독립 폴더에 모듈과 run001만 복사했다. Git/모델/실행 lock 없이
run001 verify/report와 run002 신규 생성/verify/report를 실행하고 두 버전 결과의
byte 일치를 검증했다. `.runner.lock`은 버전 관리하지 않는 실행 파일이므로 부모
패킷의 재현 hash 목록에서만 제외하고 실제 원본 파일은 그대로 보존했다.

`preservation-before.json`, `preservation-final.json`: run001 전체(무시된 lock 포함),
기존 Naive/Document Chunking 추적 파일 및 청킹 누적 ledger 등1375파일, plan의 기존
dirty4파일 hash 동일. run001의 파일 목록도 동일. 새 네트워크/모델/서버 명령은 실행하지 않았다.

## 실제 화면 검증 차단 — C1 미완료

새 HTML을 실제로 보기 위해 CUA의 `createBrowserTab("iab", "file:///.../run002/review.html")`
호출을 시도했으나 브라우저 URL 정책이 거부했다. 반환 이유는
“requested URL protocol is not allowed. Allowed protocols: http:, https:”.
도구는 우회/다른 브라우저 경로/직접 CDP 등을 금지했으므로 시도하지 않았다.
서버를 새로 시작하거나 기존 서버를 변경하지 않았다.

실제 렌더링, 좁은 화면 줄바꿈/가로 넘침, Tab/Enter/Space로 접기 동작,
새 보고서를 사용자 화면에 여는 것 모두 **미검증**이다. 소스의 반응형 CSS·focus-visible·
기본 details/summary 및 HTML 구조 검사는 PASS이지만 이를 실제 화면 PASS로 간주하지 않는다.
C1 및 P021 전체 완료는 이 확인 전까지 남겨 둔다.

후속 수동 확인: 새 HTML을 로컬 브라우저에서 열어 (1) 질문→주장→펼친 인용 순서,
(2) 기본 닫힌 실험 기록, (3) 약375px 폭에서 줄바꿈/가로 넘침,
(4) Tab으로 summary에 이동 후 Enter/Space로 열기/닫기,
(5) 이전 보고서/금액 미명시 항목의 원문 링크를 확인하고 관찰 근거를 기록한다.
사람이 화면을 확인하는 것과 정답 후보를 승인하는 것은 별개다.

## 개발 중 발견·수정

초기 부모 파일 인벤토리에 Git 미추적 `.runner.lock`이 포함되어 새 clone에서
패킷 hash가 달라질 수 있음을 코드 점검에서 발견했다. 새 검토본의 provenance 목록에서
이 실행 lock만 제외하고, 원본 보존 검증에는 계속 포함했다. lock 없는 독립 복사/재생과
추가 회귀 테스트로 수정 검증했다. run001이나 과거 실패 기록은 수정하지 않았다.

P013/NLI/Hybrid/P020는 실행하지 않았다. 이 개정이 원래 모델의 실제 질문 정확 인용
0/8 결과를 성공으로 바꾸지는 않는다. 답변 의미/평가기 품질을 새로 측정한 결과가 아니다.
