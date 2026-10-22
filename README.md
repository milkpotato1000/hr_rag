# hr_rag

HR 규정 문서에 근거해 질문에 답하고, 근거가 부족하면 담당자에게 연결하는 RAG 에이전트 프로젝트입니다.
기획·개발은 linked Git worktree로 분리하며 제품 구현은 아직 시작하지 않았습니다.

## 작업 위치

| 폴더 | 브랜치 | 역할 |
| --- | --- | --- |
| `hr_rag` | `main` | 릴리스 기준. 명시적 승격 요청 시에만 변경 |
| `../hr_rag-plan` | `plan` | 요구사항, 계약, P번호 작업 기획 및 준비 검토 |
| `../hr_rag-dev` | `dev` | 채택한 계획 구현, 검증, 실행 로그 |

세 폴더는 하나의 Git 저장소를 공유하는 linked worktree입니다.
개인 공개 저장소는 <https://github.com/milkpotato1000/hr_rag>이며 원격 이름은 `personal`입니다.
plan/dev만 게시하며 main의 push와 승격은 별도 명시 요청이 필요합니다.

## 시작하기

- plan 폴더에서 “다음 작업 기획해줘”와 제품 목표를 요청합니다.
- dev 폴더에서 “다음 큐 진행해줘”를 요청합니다.
- 큐 조회: `python3 scripts/work_queue.py --owner all`
- 개발 계약 확인: `python3 scripts/contract_guard.py check`

[프로젝트 기획](docs/planning/project-brief.md)과 [아키텍처 방향](docs/architecture/system-design.md)을 확인합니다.
첫 개발 큐는 [P001 합성 HR 문서와 검색 평가 기반](docs/planning/plans/P001.md)이며 준비 완료·미착수입니다.
plan 또는 dev 폴더에서 [작업 흐름](docs/process/work-queue.md)을 따릅니다.

## 계약과 증거

`docs/planning/`, `docs/architecture/`, `config/semantics/`와 하네스 규칙은 plan이 관리합니다.
필요한 문서는 첫 기획 시 작성합니다. dev는 정확한 plan 커밋을 채택한 뒤 구현하며,
P카드의 실행 상태·체크 표시·추가 로그만 수정합니다.
검증 근거는 `docs/verification/` 또는 `docs/progress/`에 커밋합니다.

새 clone에서는 plan/dev 브랜치를 가져오고 작업 폴더를 준비한 뒤,
dev에서 `python3 scripts/contract_guard.py install`로 로컬 훅을 설치합니다.
채택 기록은 `.harness/adopted-plan.json`에서 확인합니다.
로컬 훅은 실수 방지용이며 서버의 접근 통제는 아닙니다.

공개 저장소에 비밀키·토큰·개인 인사 데이터·비공개 문서를 커밋하지 않습니다.
