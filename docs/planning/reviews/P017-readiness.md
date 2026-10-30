# P017 준비 검토

2026-10-30 사용자 “이대로 플랜 작성 후에 작업 시작” 요청으로 준비 완료. 작업 범위는 숫자 입력/도움말/성공 이력 A/B와 그 실제 core/API 연결이다. P007 완료 dev a37d4cd를 읽었고 dev 작업 트리는 clean이다. 계획의 다른 네 파일 미커밋 수정은 기존 작업으로 보존한다.

읽은 연결점: web_chunking/app.js/index.html, experiment_common.config, chunk_core, serve_chunking.start_job/compare/catalog, retrieval_core.identity, model_runtime.Ledger, run_llm_repetitions.one, 기존 테스트. UI만 변경하면 설정이 무시되므로 core 전달과 versioned config/실제 prompt hash를 검증 조건으로 포함했다.

Naive web_compare/index.html와 serve_compare.py에서 문자 예산 min1/max24000/default8000 확인. 새 검색 비교도 이 숫자를 사용하되 top20 예산 시뮬레이션이라는 의미는 유지한다.

계획에 방식별 수치 범위·추천/한계 구분·기존실험 보존·실제 모델 한정 실행/누적 예산과 채택/검증 경계를 고정했다. LLM context8192 및 출력1024는 유지하고 동적 payload별 입력상한 검사/최대길이 검증을 요구한다. 모델 advertised 최대 context를 현재 실행 설정과 혼동하지 않는다. 검증 완료 전 실제 실행 PASS를 주장하지 않는다.

준비 확인: queue의 새 요청 대기0, P007 완료, 필요한 로컬 source/model/가상환경·저장 이력 존재, ledger pending/unresolved 없음과 충분한 잔여 한정 검증량 확인. C1~C4는 모두 미체크이며 dev exact adoption 이후 구현/회귀/브라우저 및 실제 모델 검증 증거로 완료한다. P013/P014 미완성 계약을 수정하거나 완료로 표시하지 않는다.
