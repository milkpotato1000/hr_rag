# P023 필수/보충 검토본 — 구현·오프라인 검증 및 사용자 화면 확인 완료

2026-11-05. READY plan5d3e47774a162e235b7886298a947dccb2be662d를5d12fc6에서
정확 통합·채택했다. P0224/4 완료 후 P023만 진행했다. 모델/다운로드/서버 변경0회다.

run004는 schema3/p023-core-supplement-v1이다. 질문10·원자 주장57·판정18개 및 기존
claim 객체 전체(ID/text/source/answer_span)와 원래 answer를 유지한다. 필수38/보충19,
질문별6/4,3/0,8/1,2/4,4/0,3/4,4/4,8/2,0/0,0/0으로 완전 분할한다.
필수/보충 답변은 해당 문장을 원래 순서로 연결한 별도 파생 필드이며 기존 span을
그룹 답변에 재사용하지 않는다. gt09/10의 빈 필수답변을100% 정답으로 표시하지 않는다.

## 결과와 정책

- packet.json: answer_rubric의 의도/역할·사유·보충 종류/설명 연결, 파생 답변과 scope 개수.
- scope-audit.json/scoring-policy.md: exact plan의 동결 바이트. 외부 plan 없이 검증한다.
- scope-mapping.json:57개 기존 객체와 분류의 일대일 대응. 기존 ID 변경 없음.
- review.html: 질문/의도 → 필수 답변·주장·근거 → 보충 안내·주장·근거. 분류 사유와 보충도 사실 검증 대상이라는 안내를 펼쳐 표시한다. 기술/과거 이력/예시 상세는 기본 닫힘.
- core P/R/F1과 전체 생성의 E/U/C, 보충 누락 제외·추가 오류 경고·미확정/보류와 고정 기대10예시를 표시한다. 실제 평가기/매칭/LLM 채점은 구현/실행하지 않았다.
- prior_human_claim_reviews는 run003 gt01 첫5개 직접 승인만 정확한 parent/ID/text/source와 보존한다. 새 전체 패킷/질문/판정 human_approval은null이다. 사람 승인 원장은 생성/수정하지 않았다.

## 검증

unit-tests-final.log: 기존32개 + 새9개 =41개 PASS.57개 원본/그룹 파생·완전 분할·의도 연결·
사유/정책 고정·미명시·5개 역사와 전체 미승인·모델 전 경로 거부·미지정/알 수 없는 버전·
손상 parent/audit/policy·덮어쓰기/HTML·manifest 변조 거부를 검증했다. 오프라인 생성과
재생 테스트에서 socket 생성을 차단했다.

초기 실행은40개 PASS/1개 FAIL이었다. 테스트가 동결 정책에 없는 문자열 ‘전체 생성 사실’을
요구했다. 실제 정책의 ‘필수/보충/추가 생성 사실 전체’로 정확히 대조하도록 테스트만 고쳤다.
정책/출력 바이트를 바꾸지 않았으며 실패 출력은 unit-tests-initial.log에 보존한다.

scope-review.json에 질문별 전수 분류와 의도/사유를 기록했다. claim.source는 parent의
canonical 검증을 통과하며 새 JSON/HTML에서도 동일하다. 정책상 보충의 필수 연결은
비어 있고 gt01-c07의 설명 대상은 gt01-c04-a1이다.

offline-replay.json: preparation 전체를 임시 독립 폴더에 복사했다. 외부 plan/Git/모델 없이
run001~004 verify/report, run004-replay 새 생성의 모든 파일 byte 일치를 확인했다.
preservation-before/final.json: run001~003 포함 기존1384파일·plan dirty4파일의 hash와
세 run 파일 목록을 보존했다. 과거 실패·모델 raw replies/ledger·원문은 변경하지 않았다.

## 실제 화면 관찰 미완료 — C2

기존 file URL 도구 정책은 새 탐색과 이미 열린 파일 읽기를 차단했다. 이 차단 경로를
반복하거나 별도 서버·다른 브라우저 표면·직접 CDP로 우회하지 않았다. run004 자체의
실제 화면·좁은 폭·키보드 동작은 아직 관찰하지 않았다. 과거 run003의 관찰을 승계하지 않는다.
ui-status.json에서 이를 구조 검사와 구분한다. 구조 검사는 펼친 인용75개(57+18),
기본 닫힌 details84개·분류/사유/JSON 일치·정책10예시를 확인했지만 실제 UI PASS는 아니다.

새 보고서에서 확인할 것: 필수38/보충19 및 질문별 그룹/사유, 펼친 인용과 접힌 실험 기록,
좁은 창의 줄바꿈·가로 넘침, Tab 이동 후 Enter/Space 열기·닫기. 실제 사용자 관찰을
받으면 대상 packet/hash와 관찰 범위를 별도로 기록하고 C2를 완료한다. 정답 내용 승인과
화면 동작 확인은 서로 다른 기록이다. 전체 완료 전 C2는 미완료로 유지한다.

## 전달

delivery.json에 새 보고서의 절대 경로·패킷/manifest 파일 hash 및 개수/미승인을 기록한다.
p013-handoff.md에 정책과 분모·미확정/추가 오류·승인 경계를 인계한다. P013은DRAFT이며
실제 평가기/모델/P014/P020/Hybrid/main/하네스는 변경하지 않았다.

## 후속 실제 사용자 확인 — 2026-11-05

사용자가 run004 확인 질문의 1번(직접 확인했고 네 항목 모두 정상)을 선택했다.
`run004-user-ui-observation.json`에 대상 packet/manifest hash와 네 항목 PASS를 기록했다.
기존 C2 FAIL 및 ui-status.json은 당시 미관찰 증거로 보존한다. 이번 확인은 사용자의
직접 관찰이며 Codex 브라우저 검증이나 전체 정답 승인이 아니다. P013은 DRAFT를 유지한다.
별도 요청한 도구 차단 진단은 browser-policy-diagnosis.md에 기록했다. 원인은 file URL
정책 거부이며 해제 방법은 확인하지 못했다. 정책 해결 완료로 표시하지 않는다.
