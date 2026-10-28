# 2026-10-28 새 요구 plan 경유 하네스 검토

사용자 요청: dev에서 새로운 요구가 나오면 반드시 plan을 거치도록 하네스를 추가한다. 이 요청은 프로젝트 하네스의 작성·검증·dev 적용을 포함한다. 제품 기능 P010/P007/P008은 초안을 유지하며 착수하지 않는다.

## 결정

- dev 역할을 유지하며 새 범위는 `scripts/plan_intake.py request`로 기록한다. dev가 스스로 plan 폴더로 이동해 준비 검토를 대체하지 않는다.
- plan은 커밋된 dev 요청을 읽고 보호된 `docs/planning/request-decisions/`에서 요청 hash·연결 P번호·판단 근거를 기록한다. 요청 기록과 기획/승인 책임을 분리한다.
- 큐는 기존 P 작업 순서를 유지하며 별도 `plan_requests`/미검토 표시를 제공한다. 연결된 초안은 실행 승인되지 않는다. 기존 보호 계약과 정확한 SHA 채택 절차를 유지한다.
- 기존 요청은 수정/삭제하지 않고 정정 요청을 추가한다. hook은 worktree/index/commit에서 기록 형식과 변경 여부를 검사한다.
- 범위 안 수정·검증과 개념 설명은 새 기능 요청과 구분한다. 미검토 요청이 unrelated 승인 작업을 전부 차단하지 않는다.
- 파일 기반 접수는 다른 채팅에 자동 메시지 전송·기획·구현을 허가하지 않는다. 사용자에게 매번 인계 승인을 다시 요구하지 않는다.

## 변경 경로

`AGENTS.md`, `docs/process/workspace-AGENTS.md`, `docs/process/work-queue.md`, `docs/process/plan-intake.md`, `.harness/policy.json`, `scripts/plan_intake.py`, `scripts/work_queue.py`, `scripts/contract_guard.py`, `tests/harness/test_plan_intake.py`.

상위 컨테이너 `AGENTS.md`에도 같은 역할/접수 규칙을 반영했다. 이 로컬 진입점은 Git 밖이며, 다른 컴퓨터에서는 추적된 workspace-AGENTS 문서로 복원한다. 개인 공용 스킬과 main 릴리스는 변경하지 않는다.

## 검증

- 프로젝트의 새 실제 Git fixture 테스트 `python3 -m unittest discover -s tests/harness -v`: **12 PASS**. 커밋된 dev 요청만 plan에 노출, dev의 검토 위조 차단, 요청 수정/삭제 거부, 누락 카드 거부, 요청 hash 불일치 재검토, 정확한 채택, 초안 실행 방지, 새 plan 커밋과 무관한 기존 dev 작업 보존을 확인했다.
- 사용한 plan-dev-harness 스킬의 번들 테스트: **31 PASS**. 번들 자산 회귀이며 프로젝트 구현 테스트와 구분한다. 스킬 파일은 수정하지 않았다.
- 기존 프로젝트 큐: plan 다음 P010, dev 승인 작업 없음, 새 구조화 요청 0건. 이전 일반 피드백을 자동 재등록하지 않는다.
- `git diff --check`, 문서 로컬 링크 점검 통과. 제품 코드/데이터/모델은 변경하지 않았고 제품 모델 E2E는 재실행하지 않는다.
- dev 통합은 이 계획 커밋과 변경 경로 검토를 근거로 정확히 adopt한 뒤 worktree/index/HEAD와 큐·훅을 검증한다.

## 한계

자유 형식 대화나 코드 diff가 새 요구인지 자동 판정하지 않는다. 이를 분류·접수하는 책임과 역할 경계는 AGENTS 규칙에 둔다. Git 쓰기 권한이 동일한 에이전트의 모든 우회를 막는 원격 권한 통제라고 주장하지 않는다. 실제 검사는 기록의 형식/불변성·plan 소유 경로·채택 계약을 보장한다.
