# P029 준비 검토 — 2026-11-27

READY, 선행 P028 완료 전 대기. P028 역시 P027 완료 후 작업이며 현재 둘을 완료했다고 주장하지 않는다. work-queue의 READY/선행대기 규칙과 사용자 프론트엔드·범용 교육 패키지 goal에 따라 후속 구현 계약을 준비했다.

기존 P007/P017 index.html/app/server는 fixed source-v4·기존 ledger에 묶여 있다. 이를 일반 입력으로 풀면 기존 평가 재현을 깨므로 새 package UI가 실제 P025/P026/P027 코어를 호출하도록 한다. 기존 UI는 보존한다. P026 result의 candidates/contexts/excluded/answer/citations/metrics·P027 current snapshot origin·P028 resource/console 계약을 읽고 재사용 경계를 정했다.

server CLI/등록경로·파일/secret 경계, API endpoint/schema, single active job·idempotency·restart interrupted, preview/live flags, UI 단계/지원 상태·비교/인용/페이지 window, 실제 browser·wheel 검사와 완료 기준을 계약화했다. 직접 Drive 링크 입력과 generation 모델 설정 form을 포함한다. 인증/endpoint는 CLI 등록 경계를 유지하고 typed memory connector와 불변 profile clone으로 연결한다. 실제 core 연결을 fake production 응답으로 바꾸지 않는다. 테스트용 실행은 자동 test_fixture로 표시한다.

P013/P014/P008 평가 순서를 해제하지 않으며 평가 UI/NLI/Hybrid를 완료 처리하지 않는다. 현재 없는 점수는 N/A다. 실제 모델/계정/키 실행 없이 UI 코드/합성 E2E/표시를 개발할 수 있다. 개발 검증용 loopback server와 허용 browser를 사용하되 기존 정책 거부가 있으면 우회하지 않는다. actual browser 기준은 완료 조건에 유지하고 단순 DOM/assert나 과거 run004 확인으로 대체하지 않는다.

현재 goal과 이 프로젝트의 준비·직접 전달 위임에 따라 기존 dev에 후속 인계한다. P028 완료 커밋/push 이후 exact adoption하고 착수해야 한다. P028 실제 설치 구조와 차이가 있을 때 제품 계약을 조용히 바꾸지 않는다. normal personal/dev 전달만이며 main/public hosting은 범위 밖이다. Dense/Hybrid/리랭커/실모델 평가·최종 설정 UX가 남으면 전체 goal은 계속 미완료다.
