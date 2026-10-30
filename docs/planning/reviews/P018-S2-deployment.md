# P018 S2 배포 검토

2026-10-30. 사용자 “작업들 쭉 이어서 가” 및 기존 P018 S1/S2 인계 승인 범위에서 검토한다.

검토한 dev 제안 commit: `a614a1a431180c6d7e606a23d734cc24469dea70`.
원본 release: v0.1.0 `803d658a8c61dc6aa007645a98d4160b16746faa`.

## 확인 및 배포

- 커밋된 manifest와 runtime.patch, 후보 두 파일, 추가 회귀 테스트를 읽었다. 두 스크립트는 기존 before hash와 일치하는 위치에만 적용하며 **고정 upstream asset과 byte 동일**임을 다시 검사했다.
- `scripts/plan_cards.py`와 `scripts/plan_intake.py`의 `Z` 정규화만 배포한다. 후보 hash는 각각 `d16884698f9555d5cbdb123e50177e43c00d3dc78d4057b06669efd0932add14`, `c49bbb3d9a58c3a1b7b3967cc302effd40c2b82621ebc6cff15a77509fcdd4f8`이다.
- 검토한 `tests/harness/test_timestamp_guards.py`를 제안 원본 그대로 배포한다(hash `bfbdb9c47136fa5e865377ecfa34690c608ac179dbbf38465bef88aaf68282aa`). 기존 intake fixture 상속, Z/offset/무시간대, 실제 Git hook의 보호/허위 완료/로그 재작성/마지막 FAIL 거부 및 큐 읽기를 검사한다.
- dev 증거는 Python3.9.6 기존 intake12 PASS, 구형 코드에서 추가 회귀 3실패 재현, 후보23 PASS, release bundled51 PASS를 기록한다. baseline-regression 실패는 보존됐다. 같은 intake 테스트가 상속/별도 실행돼 겹치므로 합계를 고유 테스트 수로 더하지 않는다.
- plan은 커밋된 제안의 검토·배포만 수행한다. source 실행 검증은 S1 dev 기록을 검토한 것이며 plan이 제품/모델 테스트를 재실행했다고 주장하지 않는다. 최종 설치본 테스트는 S2 dev가 수행한다.

## dev S2 인계 조건

이 문서를 포함한 정확한 plan commit을 통합·adopt한 뒤 최종 HR 회귀 및 guard worktree/index/HEAD를 확인한다. 계획 본문과 원래 C1~C4는 그대로다. 기존 S1 실행 로그를 보존하고 다시 구현하거나 실패를 삭제하지 않는다.

tracked workspace 진입 문서를 로컬 컨테이너 AGENTS.md에 반영하고 별도 사용자 로컬 규칙이 있다면 보존한다. 이 Git 외부 변경은 원격에 포함되지 않는다고 명시한다. 프로젝트 CLAUDE import/규칙/훅 경로를 확인한다. 기존 main·개인 스킬·하네스 개발 프로젝트·제품·모델 ledger·서버는 건드리지 않는다.

최종 실제 설치 hash·manual integration·기존 custom 차이와 테스트/보존/큐/정상 push 증거를 커밋한 후에만 P018 C1~C4 완료로 표시한다. 새로운 설치 manifest를 만들거나 설치형 관리 대상으로 위장하지 않는다. S1 proposal 경로는 역사 증거로 보존한다.
