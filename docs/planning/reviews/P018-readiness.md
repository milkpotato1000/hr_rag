# P018 준비 검토 — 정식 버전과 역할 분리를 보존한 업데이트

2026-10-30 / 준비 완료. 사용자 직접 응답 “P018 확정 후 dev에 전달·착수”로 현재 HR RAG의 기존 dev 인계·실행 범위를 확인했다. 임시 사이드 채팅 원문 조회는 호스트에서 지원되지 않아 그 전달문만으로 메시징 권한을 간주하지 않았고 메인 사용자 응답을 근거로 한다.

## 실제 확인

- GitHub connector `/repos/milkpotato1000/plan-dev-harness/releases/latest`, `gh release list`, 공개 `git ls-remote`를 대조했다. 최신 정식은 [v0.1.0](https://github.com/milkpotato1000/plan-dev-harness/releases/tag/v0.1.0), published_at `2026-10-29T02:54:28Z`, draft=false/prerelease=false다. annotated tag object `1aa78969b0050269fed8a5a30232779c85f9c7dd`, peeled/main `803d658a8c61dc6aa007645a98d4160b16746faa`.
- 로컬 release checkout은 해당 commit이며 깨끗하다. 소스는 `git show <exact SHA>:assets/<path>`로 읽어 이동하는 브랜치 파일과 혼동하지 않았다. 개발본 dev `6b77a5d6cc10b3345a510c50bdff88336998de8c`의 direct-handoff 문서는 의미 참고만 했으며 그 런타임을 설치하지 않았다.
- [9개 파일 비교와 hash](p018/source-comparison.json): 6개 동일, 2개 timestamp 1줄 차이, 1개 HR 전용 예시 경로 차이. guard/queue/hooks/template의 기존 동작을 교체할 이유는 없다. custom policy/AGENTS는 별도 프로젝트 규칙으로 보존·보완한다.
- 설치 manifest 없는 legacy이고 공식 installer preview가 `scripts/plan_intake.py` 충돌로 exit1 했다. apply하지 않았으며 거부는 예상된 안전 동작이다. 실제 설치/보호 파일 교체 성공으로 보고하지 않는다.
- 현재 plan `48011d5`, dev `229a080`, P017 완료4/4, P007 완료6/6. dev 기존 실행 가능 승인 작업 없음, pending intake0. plan의 평가 관련 미커밋 네 파일은 hash를 고정했다.
- 세 worktree의 공통 구조, 기존 `.githooks` 설정을 확인했다. main baseline은 `2ebd724ce925962f7a2e67df7bdb63e1eab569d7`이며 변경하지 않는다.

## 역할 충돌 해소

런타임 스크립트·tests/harness는 이미 plan 보호 대상이다. dev가 보호를 풀거나 우회하지 않도록 **S1 임시 복사본의 변경안/검증 → plan의 커밋된 제안 검토·배포 → S2 exact adoption·적용**으로 고정했다. 이는 plan의 런타임 대리 개발이 아니라 기존 소유권을 유지하는 배포 검토이며, 실제 구현 제안·테스트·로컬 적용·완료는 dev가 수행한다. 이 단계 구분이 없는 직접 덮어쓰기는 승인 범위 밖이다.

plan은 현재 AGENTS·CLAUDE import·workspace 문서·direct-handoff·policy와 이 P카드만 작성한다. core script 4개·훅2개·보호 테스트는 바꾸지 않는다. S1 검증 결과가 실패하면 C1~C4 완료를 표시하지 않으며 기존 승인 범위 안에서 dev가 수정·재검증한다. 새 의미 결정은 plan에서 재검토한다.

## 검증 범위와 한계

등록 시 diff/링크/P카드·큐·보존 hash를 검사한다. source release의 과거 51tests PASS는 출처 이력이지 이번 HR 설치 검증이 아니다. dev가 현 프로젝트 후보와 최종 적용본을 검증하며 Python 버전은 실제 실행값만 기록한다. 제품·모델 실행, 서버 재시작, 개인 스킬/Claude 전역 설치, 0.2.0 개발 기능은 포함하지 않는다. 새 테스트가 필요하면 승인된 절차로 제안한다.

미결 업무 결정은 없다. S1→S2의 계획 검토는 내부 실행 순서이며 매 단계 사용자에게 재승인을 요청하지 않는다. 실제 메시지 도구 결과와 수신·adoption은 별도 인계 기록에 남기고, 이 준비 문서 자체를 전달/완료 증거로 사용하지 않는다.
