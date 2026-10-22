# hr_rag 작업 규칙

## 기획·개발 흐름

하나의 Git 저장소에 `main`(hr_rag), `plan`(hr_rag-plan), `dev`(hr_rag-dev) linked worktree를 사용한다.
실행 전 현재 브랜치, 변경 상태, 채택한 계획과 관련 계약, dev 피드백을 확인하고 기존 작업을 보존한다.
프로젝트 목표와 단계는 `docs/planning/project-brief.md`, 설계 방향은 `docs/architecture/system-design.md`를 따른다.
사용자가 지정한 HR RAG 기획 대화를 근거로 P카드별 구현 범위를 준비한다.

plan은 `docs/planning/`, `docs/architecture/`, `config/semantics/` 및 보호된 하네스 규칙을 소유한다.
새 과제는 `docs/planning/plans/P*.md`의 한 P번호를 기획부터 완료까지 사용한다.
`docs/process/work-queue.md`를 읽고 `python3 scripts/work_queue.py`로 다음 작업을 조회한다.
제품 요구가 없으면 큐를 비워두고 최초 제품 목표를 확인한다. DRAFT를 자동 승인하지 않는다.

사용자가 요청한 프로젝트 목표 내에서 plan에 준비 검토 및 dev 등록을 위임한다.
범위·선행·검증·완료 기준이 준비되면 검토 근거를 기록하고 준비 완료로 커밋·등록한다.
작업마다 인계 허가를 반복해서 묻지 않는다. 미결 업무 결정과 권한 밖의 동작은 먼저 해결한다.

dev는 정확히 채택한 계획을 구현한다. P카드는 실행 상태, 체크 표시, append-only 실행 로그만 수정한다.
완료를 위해 요구·완료 조건·기존 실패 로그를 바꾸거나 삭제하지 않는다.
구현 → 검증 → 수정 → 재검증을 수행하고, 체크마다 최신 PASS와 비어 있지 않은 커밋된 증거를 남긴다.
증거는 `docs/verification/` 또는 `docs/progress/`, 의미 불일치는 `docs/feedback/dev/`에 기록한다.

인계 방향은 plan → dev이며 `scripts/contract_guard.py adopt <정확한 plan SHA> --review-reference '<실제 검토 근거>'`로 채택한다.
dev 채택 큐가 비었으면 최신 plan에 준비된 작업이 있는지 먼저 확인하고 안전하게 통합·채택한다.
plan은 dev의 커밋된 진척을 큐로 읽으며 체크 표시를 옮기려고 임의의 dev 구현 이력을 병합하지 않는다.
plan은 dev 구현 중 다음 독립 과제를 준비할 수 있다. 다른 채팅에 메시지를 보내려면 별도 사용자 지시가 필요하다.

## 단계별 구현 폴더

제품 구현은 저장소 루트의 `1. 검색 평가 기반/`, `2. BM25 검색 기준선/`, 이후 `3. {제목}/`처럼 단계별로 분리한다.
다음 단계는 앞선 단계에서 필요한 코드·데이터·테스트를 복사·선별한 뒤 그 폴더 안에서 개발한다.
이전 단계는 기준선으로 보존하고 런타임 import·symlink·상대 경로로 다른 단계에 의존하지 않는다.
각 단계 README와 stage-manifest.json에 실행법·변경점·복사 원본 커밋·경로·hash를 남긴다.
기획·계약·증거·Git 하네스는 루트에서 관리한다. 자세한 배치와 P001 전환은 [단계별 구현 폴더](docs/architecture/stage-layout.md)를 따른다.

## Git과 공개 범위

개인 공개 저장소 `https://github.com/milkpotato1000/hr_rag` 하나만 `personal` 원격으로 사용한다.
사용자의 상시 권한에 따라 plan/dev는 정상 non-force push할 수 있다.
main의 push·승격·병합은 명시 요청이 필요하다. 훅을 우회하거나 force push하지 않는다.
로컬 훅과 검증을 실행한다. 각 clone에서 훅을 설치한다.
CI·원격 브랜치 보호·PR 강제는 이 하네스의 필수 설치 요건이 아니다.
키·토큰·개인 인사 데이터·비공개 문서를 커밋하지 않는다.

## Snowflake

Snowflake 접근은 `snow` CLI를 기본으로 한다. 브라우저는 사용자의 명시 요청이 있을 때만 사용한다.
CLI 실패 시 연결을 진단하고 차단 원인을 보고한다. 계정·DB·역할을 확인하고 다른 프로젝트의 연결을 재사용하지 않는다.
plan은 별도 허가 없이는 읽기·기획만 수행하며 dev는 채택한 계약과 승인 범위를 따른다.
비밀키는 저장소 밖의 로컬 Snowflake 설정 디렉터리에 보관한다.
