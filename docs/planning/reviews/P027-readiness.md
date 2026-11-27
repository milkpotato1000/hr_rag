# P027 준비 검토 — 2026-11-27

READY. 선행 P026의 실제 구현·완료 증거를 검토했다. exact adoption 7c88c59, 구현 5e677893730316c140b63d4379fb426172ab64c4, 완료 0252ec1731431c67172f7692b14fed7ec763821f이며 dev/personal-dev가 일치한다. 36개 테스트(신규18/P025회귀18), CLI preview 9행, 기존1475파일 보존과 실모델0을 확인했다. 이 결과를 실제 모델 품질 검증으로 확대하지 않는다.

P026 documents.snapshot/load_snapshot의 입력·identity·original bytes·페이지 계약을 읽고 optional origin의 후방 호환 확장과 불변 receipt/snapshot 연결을 확정했다. URL 수집은 단일 Drive 파일부터 제공한다. API/SDK 원자료로 다운로드/export/권한/resource key/version/checksum/OAuth를 확인했다. 지원 범위·strict schema·CLI·요청 한도·인증·credential 저장·실패·provenance·검증/완료 기준을 상세 계약에 고정했다.

OAuth SDK 후보 두 버전의 호환 조합은 아직 설치 검증 전이다. dev에 격리 설치·의존성 lock·SDK import/signature 및 fake auth 검증을 명시적으로 포함했다. 실패하면 조용히 버전을 바꾸거나 라이브 계정으로 시험하지 않는다. 설치 검증은 모델/서버 실행과 별개다. 실제 계정 로그인·파일 지정 없이도 구현/fixture 검증/설치 안내를 완료할 수 있으나 live E2E는 별도 사용자 입력과 명시 실행이 필요하다.

P013 보류는 유지한다. 임베딩/Hybrid/리랭킹 선행 변경 질문은 아직 답변이 없으므로 종전 순서를 유지한다. P027은 해당 질문과 독립인 문서 연결 증분이며 새로운 유료 서비스/모델 실행을 요구하지 않는다. 사용자 goal과 같은 프로젝트 준비·직접 dev 등록 위임에 따라 정확 READY를 기존 HR RAG dev로 전달한다. 다른 프로젝트/새 채팅/main 승격은 없다. 최종 패키지 goal은 Dense/Hybrid/리랭커·평가·UI·실모델/설치 검증이 남아 완료가 아니다.
