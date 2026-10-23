# hr_rag

HR 규정 문서에 근거해 질문에 답하고, 근거가 부족하면 담당자에게 연결하는 RAG 에이전트 프로젝트입니다.
기획·개발은 linked Git worktree로 분리하며 제품 구현은 아직 시작하지 않았습니다.

## 작업 위치

코덱스에서는 상위 `hr_rag/` 하나를 프로젝트로 엽니다. 그 안에 아래 세 작업폴더를 둡니다.
상위 폴더에는 `.git`을 두지 않으며, Git과 프로젝트 스크립트는 해당 하위 폴더에서 실행합니다.
표의 경로는 각 하위 작업폴더 기준입니다.

| 폴더 | 브랜치 | 역할 |
| --- | --- | --- |
| `../hr_rag_main` | `main` | 릴리스 기준. 명시적 승격 요청 시에만 변경 |
| `../hr_rag_plan` | `plan` | 요구사항, 계약, P번호 작업 기획 및 준비 검토 |
| `../hr_rag_dev` | `dev` | 채택한 계획 구현, 검증, 실행 로그 |

세 폴더는 하나의 Git 저장소를 공유하는 linked worktree입니다.
개인 공개 저장소는 <https://github.com/milkpotato1000/hr_rag>이며 원격 이름은 `personal`입니다.
plan/dev만 게시하며 main의 push와 승격은 별도 명시 요청이 필요합니다.

## 시작하기

상위 프로젝트에서 “기획해줘”는 `hr_rag_plan/`, “구현해줘”·“검증해줘”·“다음 큐 진행해줘”는
`hr_rag_dev/`를 사용합니다. 양쪽 작업은 plan 준비 검토 → dev 통합·정확한 채택 순서로 진행합니다.
각 작업폴더의 AGENTS.md와 기존 P카드·검증·Git 규칙을 따릅니다.

plan/dev 채팅을 별도로 만들 때에도 같은 상위 프로젝트를 사용합니다. 각 채팅의 초기 지시에 역할과
작업폴더를 고정하므로 “다음 작업”을 요청하면 해당 역할로 이어갑니다. 새 채팅은 최초 규칙·상태·큐를
읽기 전용으로 확인하고 다음 요청을 기다립니다. 기존 채팅이 있으면 새 채팅 제목에 구분 표시를 붙입니다.

새 컴퓨터에서 같은 폴더 구조를 만든 뒤, 상위 `hr_rag/`에서 다음 명령으로 진입 규칙을 복원합니다.

```sh
cp hr_rag_plan/docs/process/workspace-AGENTS.md AGENTS.md
```

진입 규칙 원본은 Git으로 관리하고, 상위 사본은 로컬에서 사용합니다. 기존 상위 규칙이 있다면 내용을 통합합니다.


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
