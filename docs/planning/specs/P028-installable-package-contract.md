# P028 설치 패키지 계약 v1

READY. P027 완료 후에만 실행한다. P027의 현재 SDK 설치/import 증거를 확인했으며 최종 완료 lock을 구현 시작 시 다시 확인한다. 사용자 goal의 설치·코딩 도구 공통 실습을 위한 증분이며 P013/Hybrid 순서를 우회하는 작업이 아니다.

## 배포물과 범위

현재 저장소에는 pyproject와 LICENSE 파일이 없다. root pyproject.toml과 필요한 packaging 설정을 추가하되 자동 전체 repository 탐색을 쓰지 않는다. distribution 이름은 `milkpotato-rag-lab`, import 이름 `rag_package`, 초기 개발 버전 `0.1.0.dev1`, console command `rag-lab`로 고정한다. 이름은 PyPI 등록을 보장하지 않으며 이번 범위에서 PyPI/GitHub release/main 승격을 하지 않는다. 저장소의 권리 조건을 임의 MIT 등으로 선언하거나 기존 소스의 라이선스를 바꾸지 않는다. 모델 라이선스와 패키지 소스의 라이선스를 별개로 안내한다.

wheel에는 rag_package 실제 모듈·명시한 resource·필요 package metadata만, sdist에는 그 파일과 명시한 build 설정·패키지 안내만 포함한다. `.git`, worktree/harness/GT/evaluation/기존 단계 corpus, tests/fake 응답, venv/cache, credentials, private 산출물, docs/verification, .rag-runs는 포함하지 않는다. 경로 allowlist와 wheel/sdist inventory를 증거로 남긴다. 기존 source provenance는 필요한 metadata만 포함하고 local absolute path에 의존하지 않는다.

core runtime은 stdlib다. optional extras `pdf`는 P026 pypdf pin, `drive`는 P027의 실제 검증된 OAuth SDK pin을 재사용하며 `all`은 둘의 합이다. 의존성 설치가 모델/Drive 로그인/외부 API 실행을 시작하지 않는다. 별도 dev build lock은 PyPA build 1.6.1/setuptools 84.2.1 후보와 transitive 버전/hash를 고정한다. 실제 호환성/설치 검증을 수행하고 임의 대체하지 않는다. 새 격리 환경에서만 공식 PyPI package를 설치하며 기존 venv/global Python/locks는 변경하지 않는다. build backend/network와 application runtime/network를 시험 기록에서 구분한다.

Python>=3.10, 현재 지원 storage primitive가 있는 macOS 및 Linux 대상이다. 실제 macOS 새 venv 시험과 Linux 구현/미검증 상태를 구분한다. Windows/미지원 OS는 doctor에서 actionable unsupported로 표시하고 OS-independent로 광고하지 않는다. Python3.10 문법 검사와 실제3.12 실행을 모든 Python runtime 검증으로 표현하지 않는다.

## 설치 후 명령

`rag-lab`은 기존 `python -m rag_package`와 동일 main을 사용한다. LLM-only CLI `python -m rag_package.llm`도 설치 후 동작한다. 기존 명령/JSON/schema/기본 preview/명시 execute는 유지한다. module 경로와 package resources는 importlib.resources 등 설치 위치 독립 방식으로 읽고 저장소 상대 경로·개발자의 home·현재 cwd를 가정하지 않는다. PDF worker subprocess도 설치된 interpreter/module에서 동작해야 한다.

`rag-lab init --out NEWDIR`는 새 실습 디렉터리만 생성한다. 기존 경로를 수정/덮어쓰거나 Git/init/harness 설치를 수행하지 않는다. P026 staging/no-clobber 원칙을 재사용한다. 인터넷/모델/API/Drive/OAuth 호출과 secret env 읽기는 0이다.

resource에서 선택한 합성 TXT/MD 문서2개, local/API별 LLM 설정 예시, 규칙청킹3종 RAG 설정, questions, 가짜 Drive config 예시, 한국어 START_HERE.md, `.gitignore`(.rag-runs와 local credentials)를 복사한다. 원본 선택 SHA/path/hash와 변경 내역을 package resource manifest에 기록한다. 기존 23페이지 HR PDF 전체를 wheel에 넣지 않는다. 최소 합성 PDF를 포함한다면 생성/파싱 근거와 가상자료 표시를 남긴다. 상대 경로가 생성 디렉터리 안에서 완결되어야 한다.

샘플 LLM 설정은 preview 가능한 schema를 따르되 기존 개인 Ollama alias/digest를 누구에게나 설치된 표준 모델로 표현하지 않는다. local/API 구분과 사용자가 바꿀 모델·HF ID·revision/digest·key env를 안내한다. example validation_status는 미검증 예시다. json_object가 generation profile의 기본이며 evaluation role이 샘플 실습에서 호출되지 않는다. 예시 표식이 남아 있으면 실행 전 configuration_required로 거부하고, 사용자가 설정한 digest가 runtime 실제값과 다르면 기존 fail-closed 동작을 유지하며 자동 lookup/교체/다운로드하지 않는다. placeholder 또는 과거 lock 예시 때문에 live 실행 준비가 완료됐다고 표시하지 않는다.

`rag-lab doctor [--config RAG_CONFIG]`는 Python/platform/package version, optional dependency 설치/정확 pin, storage primitive 지원, config 존재/schema 및 명시 설정상 지원 여부를 JSON 또는 읽기 쉬운 출력으로 제공한다. secret 값/키 존재 여부/전체환경/credential 파일 원문/문서 본문을 읽지 않는다. 서버/모델 가용성·API key·Drive 접근은 not_checked이며 doctor PASS를 live ready로 표현하지 않는다. missing optional dependency는 관련 기능 unavailable로 표시하고 core 텍스트 실습을 차단하지 않는다. 잘못된 config/필수 runtime 불충족은 nonzero, optional 미설치만으로는 core 실패하지 않는다. 아래 JSON schema/exit code를 따른다.


### doctor와 예시 설정의 확정 계약

출력 schema_version=1, package={name,version}, python={version,supported}, platform={name,storage_supported}, optional_dependencies={pdf:{installed_version,required_version,status},drive:{packages:[{name,installed_version,required_version}],status}}, config={status,reasons}, live_checks="not_checked", network_requests=0, secrets_read=0, status 필드를 반환한다. dependency status는 available/missing/version_mismatch, config status는 not_supplied/valid/example_requires_configuration/invalid다. status는 ready_for_offline/needs_configuration/unsupported/error. exit0은 필수 runtime/core와 제공 config가 유효한 경우(선택 extras 미설치 가능), exit3은 예시 설정을 실제 모델값으로 바꿔야 하는 경우, exit2는 잘못된 입력/필수 runtime 실패다. 추가 human-readable 설명은 JSON 안에 넣으며 raw exception/path secrets는 출력하지 않는다. live_checks는 항상 not_checked다.

init의 local profile은 모델명 `EXAMPLE_OLLAMA_MODEL`, HF 후보 Qwen/Qwen3-8B, expected_digest 64자리 0으로 만들고 검증된 모델로 표현하지 않는다. API profile은 `EXAMPLE_API_MODEL`과 key env 이름만 둔다. 양쪽 identity.validation_status="example_requires_configuration"을 넣는다. P025 validate/preview는 schema로 받아 실습이 가능하되 invoke는 실제 env/transport 조회 전에 해당 generation/evaluation profile의 이 표식 또는 EXAMPLE_ model을 `configuration_required` 오류로 거부한다. 이미 존재하는 실제 사용자 설정/기존 예시의 의미를 변경하지 않는다. 학습자는 본인 모델·실제 digest/HF 출처·API model을 설정하고 validation_status="user_configured_unverified"로 바꾼다. 이를 live 검증 완료로 주장하지 않는다. doctor는 이 예시 표식을 명시적으로 알려 주고, 샘플 기본 실습은 preview만 수행한다.

optional dependency metadata 검사는 importlib.metadata로 수행하고 설치되지 않은 SDK를 import하거나 인증정보를 읽지 않는다. storage_supported는 OS와 primitive 존재를 검사한 결과이며 실제 source 파싱 성공이나 디스크 전체 쓰기 권한 보장은 아니다. package 버전은 단일 버전 파일/metadata에서 일관되게 공급하며 `rag-lab --version`과 module CLI가 같은 값을 표시한다.

## 안내와 실제 사용

`docs/learning/rag-package/install.md`와 package 전용 README에 가상환경 만들기→현재 dev의 고정 commit 소스로 build/install 또는 생성 wheel 설치→init→doctor→preview 실습을 설명한다. 설치 가능한 PyPI 이름이라고 가정하는 `pip install milkpotato-rag-lab` 안내는 쓰지 않는다. Git default main에 새 모듈이 있다고 안내하지 않고 검증한 dev ref/SHA를 사용한다. 고정 commit, 패키지 버전, wheel hash를 기록한다. source checkout 없이 wheel만으로 실습할 수 있어야 한다.

Claude Code와 Codex에 같은 실습 폴더를 열고 요청하는 짧은 한국어 예시를 각각 제공한다. 해당 코딩 도구/CLI를 자동 설치·로그인·호출하지 않는다. AGENTS.md/CLAUDE.md와 각 저장소 governance를 존중하고 이 실습 생성이 기존 하네스/프로젝트 규칙을 덮어쓰지 않음을 설명한다. '두 도구에서 실행 가능'은 공통 CLI 구조를 의미하고 두 제품의 실제 UI 자동 조작을 검증했다고 주장하지 않는다.

실행 가능한 기능/다음 구현/라이브 미검증을 분리한다. 처음 실습은 API키 없이 문서→청크→검색→전달 예정 문맥까지다. 답변을 실제 얻으려면 사용자가 로컬 모델 또는 선택 LLM API를 설정하고 명시 execute해야 한다. API에 문서가 전송되는 범위·키 env·비용 미측정, Drive 로그인 권한, 데이터 보관, 실패 후 자동 재요청 없음과 기존 P013 보류를 함께 안내한다. 모델/문서 설정 절차를 전체 패키지 구현 완료와 혼동하지 않는다.

## 검증

서로 분리된 임시 build venv, core-only install venv, extras install venv를 만든다. 공식 package 설치와 로컬 artifact 설치는 허용하되 실제 모델/계정 호출·글로벌 설치·기존 venv 변경은 하지 않는다. python -m build로 sdist와 그 sdist에서 wheel을 만들고 설치 artifact hash/inventory를 남긴다. developer source가 없는 cwd, PYTHONPATH unset, clean process에서 import path가 새 venv site-packages인지 확인한다.

core-only는 --help/version/doctor/init 및 sample snapshot→3chunker build→ask-preview→compare를 실행한다. socket/env secret 접근을 차단하여 네트워크/키0을 증명한다. extras는 PDF worker 파싱과 실제 SDK import/signature를 확인하되 auth/HTTP는 fake로 대체한다. 기존 P025/P026/P027 regressions와 no-clobber/resource path/provenance/package inventory를 검증한다. 설치된 package를 tests가 source import로 덮어쓰는 실수를 피한다. fake fixture 함수는 application package에 들어가지 않는다.

실제 새 컴퓨터/새 OS까지 시험한 것으로 표현하지 않는다. macOS 동일 기계의 깨끗한 venv 검증을 정확히 보고한다. 기존 stages/evaluation/locks/GT/P013 bytes와 adoption 보존을 확인한다. C1~C3 최신 PASS·실행 로그·delivery를 normal personal/dev에 기록한다. 모델 성능·종합 UI·전체 goal 완료는 후속이다.

## 확인한 공식 근거

2026-11-27 [PyPA packaging guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/), [build 1.6.1](https://pypi.org/project/build/), [setuptools 84.2.1](https://pypi.org/project/setuptools/)를 확인했다. pyproject/build backend/wheel/sdist는 공식 패키징 구조를 따른다. 배포 이름·파일 경계·optional 구성·명령·실행 제한은 이 프로젝트 선택이다. 후보 버전 확인은 설치 호환성 검증이 아니다.

## 설치 위치 변경에 따른 credential 경계

P027의 source checkout 경로 기반 credential guard는 wheel 설치 후 site-packages를 프로젝트 루트로 오인할 수 있다. P028에서는 현재 명시 workspace/cwd와 credential 대상의 부모 `.git` directory 또는 worktree `.git` file를 검사하여 실제 Git 작업폴더 내부 credential을 거부한다. 단순히 site-packages 밖이면 안전하다고 판단하지 않는다. 기존 HR 컨테이너 경계·절대경로·symlink/0700/0600 검사를 보존한다. init sample 폴더 내부에 credentials를 저장하도록 안내하지 않는다. installed wheel + temporary Git/worktree-shaped directory의 거부와 저장소 밖 전용 credential 경로의 허용을 fake secret으로 검증한다. Git 네트워크 호출/사용자 secret 탐색은 필요 없다.
