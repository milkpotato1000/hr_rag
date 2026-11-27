# P028 준비 검토 — 2026-11-27

READY with execution dependency P027. work-queue.md의 “준비 완료 / 미착수: 선행 미완료이면 대기” 규칙을 적용한다. P027은 현재 진행 중이고 완료라고 표시하지 않는다. 실제 SDK 격리 설치/import 증거에서 google-auth-oauthlib1.5.0/google-auth2.63.1와 공식 호출 시그니처를 확인했다. P027 최종 lock/adoption/완료 ref는 실행 시작 시 다시 확인해야 한다.

기존 rag_package CLI, P025 설정/preview/invoke, PDF worker, storage primitive와 상대 예시 경로를 읽었다. pyproject/LICENSE가 현재 없고 기존 문서는 저장소 cwd와 단계별 venv를 전제하므로 wheel-only 설치·resource init·doctor가 목표에 필요한 독립 증분이다. 기존 패키지 전체를 재설계하거나 미구현 Dense/UI를 포함한다고 주장하지 않는다. PyPA와 공식 PyPI source에서 build1.6.1/setuptools84.2.1 후보를 확인했다. 실제 격리 설치/lock은 dev의 검증 범위다.

범위/명령/schema/optional deps/no-clobber/배포 allowlist/독립 설치시험/문서·비밀값·실모델 보류/완료 기준을 계약에 고정했다. 초기 샘플은 특정 컴퓨터의 모델 digest를 공용 기본으로 복사하지 않고 marked placeholder다. validate/preview는 가능하되 invoke가 env/HTTP 전에 configuration_required로 멈추도록 하여 실제 실행 가능 여부를 오인하지 않게 한다. doctor가 runtime/API 가용성을 확인한 것처럼 표시하지 않는다.

라이선스 파일이 없으므로 소스 권리를 임의 변경하지 않고 metadata에 MIT 등을 발명하지 않는다. PyPI/GitHub release/main 승격은 하지 않는다. 여기서의 배포물은 승인된 dev 브랜치와 격리된 로컬 build artifact다. 실제 타 OS·다른 컴퓨터·Claude/Codex UI 실행 검증과 동일 기계 fresh venv 시험을 구분한다.

P013 hold, 기존 실패/GT/grant, Hybrid/리랭커 선행 결정을 유지한다. 설치/샘플/의존성 검사에는 실제 모델·계정 접근이 필요 없고 기존 목표를 진전시킨다. 사용자 프로젝트 goal·준비/직접 dev 등록 위임으로 기존 dev에 queued handoff하되 현재 P027을 중단하지 않는다. 안전한 완료 커밋 이후 exact adoption/구현한다. C1~C3 전체 증거와 personal/dev 전달을 요구하며 전체 goal 완료는 별도다.

추가 설치 검토: 현재 P027 drive_config.py의 REPO/WORKSPACE는 __file__ 기준이다. wheel 설치 시 site-packages만 보호하는 것으로는 저장소 밖 credential 계약을 유지하지 못하므로, 실제 workspace/credential 부모의 Git 경계를 검사하는 후방 호환 수정을 P028 계약에 명시했다. P027 checkout에서의 범위를 깨지 않고 installed 형태에서 같은 약속을 지키기 위한 수정이다. 실제 private credential을 읽을 필요가 없다.
