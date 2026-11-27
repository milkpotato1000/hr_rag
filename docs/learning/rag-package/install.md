# 설치하고 독립 폴더에서 실습하기

`milkpotato-rag-lab` 0.1.0.dev1을 wheel/sdist로 설치할 수 있습니다. **PyPI 게시·main 승격은 하지 않았습니다.** 검증한 dev 소스는 `6921810b0414297358cffe3574ffa09ea03a305d`입니다. 이 패키지는 기본 preview로 문서→청킹→검색→전달 문맥을 확인하며, 실제 답변을 얻으려면 사용자가 모델을 별도로 설정해야 합니다.

[학습 시작점](README.md) · [패키지 안내](../../../PACKAGING.md) · [설치 검증](../../verification/p028/README.md) · [배포물 hash/inventory](../../verification/p028/artifacts.json)

## 준비와 빌드

Python 3.10 이상, macOS 또는 Linux의 지원 storage primitive가 필요합니다. 실제 설치 시험은 같은 Mac의 새 Python 3.12.14 가상환경에서 했습니다. Linux/다른 컴퓨터/Windows/모든 Python 버전의 실행 성공을 뜻하지 않습니다. Windows는 doctor에서 unsupported입니다. `python3 --version`이 3.10 미만이면 설치된 지원 Python을 선택하세요.

다음은 사용자가 별도 폴더에서 수행할 설치 예시입니다. 기존 프로젝트/venv를 변경하지 않습니다. 공식 PyPI에서 Python 빌드 의존성을 설치하는 동작이며 모델 다운로드·API 호출과 별개입니다.

```sh
git clone --branch dev https://github.com/milkpotato1000/hr_rag.git rag-lab-source
cd rag-lab-source
git checkout --detach 6921810b0414297358cffe3574ffa09ea03a305d
python3 -m venv .rag-runs/build-env
.rag-runs/build-env/bin/python -m pip install --require-hashes -r packaging/requirements-build.lock
.rag-runs/build-env/bin/python -m build --no-isolation --outdir .rag-runs/dist
```

이 명령은 sdist를 만든 후 그 sdist에서 wheel을 만듭니다. 배포파일에는 명시한 모듈·샘플·잠금/출처 metadata만 들어가며 기존 HR 규정집·GT·평가 데이터·tests·실제 문서·credential·하네스는 포함하지 않습니다. 소스 라이선스를 임의 MIT 등으로 선언하지 않았습니다. 공개 모델의 라이선스와 소스 재배포 권한은 별개로 확인합니다.

이번 검증 wheel SHA256은 `1b8efcb9e4eb13377839be142edcd66b2dbae0e973240e8fc4ee2c2dcd0183fb`입니다. 동일 소스의 재빌드 ZIP timestamp에 따라 파일 전체 hash는 달라질 수 있습니다. 독립 재빌드에서 모든 멤버 경로/bytes가 같은지 확인했고 두 파일 hash를 검증 기록에 남겼습니다. 다운로드한 동일 배포파일을 비교할 때는 반드시 해당 파일의 기록된 hash를 사용하세요.

## 소스 없이 wheel만 설치

아래 절대경로는 본인의 경로로 바꾸세요. CLI를 편하게 실행하려면 해당 새 venv를 활성화하거나 `bin/rag-lab` 절대경로를 사용합니다. venv를 저장소 밖에 만들 수도 있습니다.

```sh
python3 -m venv /원하는/새환경
/원하는/새환경/bin/python -m pip install /배포물/milkpotato_rag_lab-0.1.0.dev1-py3-none-any.whl
/원하는/새환경/bin/rag-lab --version
/원하는/새환경/bin/rag-lab init --out /원하는/새실습폴더
cd /원하는/새실습폴더
/원하는/새환경/bin/rag-lab doctor
```

core는 표준 라이브러리만 사용합니다. `rag-lab`과 `python -m rag_package`는 같은 main입니다. `python -m rag_package.llm`도 설치 후 사용할 수 있습니다. `init`은 새 폴더만 만들고 기존 파일을 덮어쓰거나 Git·하네스·코딩 도구를 설치하지 않습니다.

PDF가 필요하면 wheel 경로 뒤 `[pdf]`, OAuth helper면 `[drive]`, 둘 다면 `[all]`을 선택합니다. 예를 들면 다음과 같습니다.

```sh
/원하는/새환경/bin/python -m pip install '/배포물/milkpotato_rag_lab-0.1.0.dev1-py3-none-any.whl[all]'
```

선택 의존성은 pypdf 6.21.2/google-auth-oauthlib 1.5.0/google-auth 2.63.1입니다. 엄밀한 전이 의존성 재현은 wheel에 포함된 두 requirements lock으로 hash 검증 설치합니다. optional 미설치는 관련 기능을 unavailable로 표시하지만 텍스트 core 실습을 막지 않습니다. 설치는 로그인·모델 실행을 하지 않습니다.

## 첫 실습과 doctor 해석

생성 폴더의 START_HERE.md에 모든 상대경로가 완결된 명령이 있습니다. API 키 없이 시작하세요.

```sh
rag-lab doctor --config fixed.json
rag-lab snapshot --sources sources.json --out .rag-runs/snapshot-01
rag-lab build --snapshot .rag-runs/snapshot-01 --config fixed.json --out .rag-runs/fixed-01
rag-lab ask --run .rag-runs/fixed-01 --config fixed.json --question '생일 휴가 자격과 신청 기한은?' --out .rag-runs/answer-01
rag-lab compare --snapshot .rag-runs/snapshot-01 --configs fixed.json recursive.json structure.json --questions questions.json --out .rag-runs/compare-01
```

첫 doctor의 exit 3/needs_configuration은 예시 모델을 본인 설정으로 바꿔야 한다는 정상 안내입니다. 이후 preview 명령은 계속 사용할 수 있습니다. 자동 스크립트에서 이를 성공 exit0으로 오인하지 마세요. output_exists면 새 결과 이름을 쓰며 기존 산출물은 보존합니다.

| doctor 결과 | 의미 |
| --- | --- |
| exit0 / ready_for_offline | 필수 runtime·제공 config 유효. optional 미설치 가능 |
| exit3 / needs_configuration | EXAMPLE 모델/예시 identity를 바꿔야 실제 invoke 가능 |
| exit2 / error 또는 unsupported | 잘못된 config 또는 Python/platform/storage 지원 문제 |
| live_checks=not_checked | 서버/모델/API key/Drive 권한을 확인하지 않음 |

원문→청크 경계→검색 후보→전달/제외 문맥을 비교하세요. fixed/recursive/structure와 overlap을 한 변수씩 바꿉니다. 답변 생성·품질 평가·비용은 preview에서 미측정입니다. 현재 범용 경로는 BM25와 규칙3종이며 Dense/Hybrid/리랭커/의미·LLM 청킹은 후속입니다. [통합 UI](ui.md)는 이후 P029 소스에 추가되어 아래 고정 P028 빌드와 구분합니다.

## 실제 답변으로 넘어가기

샘플 local 모델은 EXAMPLE_OLLAMA_MODEL, HF 후보 Qwen/Qwen3-8B, digest는 64자리 0입니다. 특정 개인 Ollama alias가 사용자 환경에 있다고 가정하지 않습니다. 본인 모델명·실제 digest/HF 원본/revision/변환 정보를 기록하고 identity.validation_status를 user_configured_unverified로 바꿉니다. API는 EXAMPLE_API_MODEL과 requested_model을 실제 값으로 바꾸고 같은 표식을 변경합니다. RAG의 llm_config에 llm-local.json 또는 llm-api.json을 지정합니다.

예시 표식 또는 EXAMPLE_ 모델이 남으면 invoke는 key/HTTP 전에 configuration_required입니다. 실제 digest가 다르면 기존 검증이 거부하며 자동 lookup·모델 교체·다운로드하지 않습니다. user_configured_unverified도 live 검증 완료를 뜻하지 않습니다. generation/evaluation은 별도 역할이고 이 샘플 실습은 evaluation을 호출하지 않습니다.

사용자가 전송 범위·비용/호출 상한을 정하고 ask에 명시 --execute를 줄 때만 실제 답변을 요청합니다. API에는 질문·선택 문맥이 전송될 수 있고 비용은 미측정입니다. 키는 api_key_env가 가리키는 환경 변수로 관리하며 파일·명령 인수·Git에 값을 넣지 않습니다. 오류 후 자동 재시도/대체 provider는 없습니다. 실제 Drive는 [별도 인증 안내](drive.md)를 따르고 credential은 실습 폴더와 Git 밖 전용0700/0600에 둡니다. 실제 문서/결과도 공개 Git에 넣지 마세요. P013 보류·미소비 grant는 그대로입니다.

## 두 코딩 도구에서 학습

같은 실습 폴더를 열고 상위 AGENTS.md/CLAUDE.md를 존중하게 합니다. 두 제품을 자동 설치·로그인하거나 실제 UI를 검증하지 않았습니다. 공통 CLI 구조를 이용하는 요청입니다.

Codex 요청:

> 현재 폴더와 상위 AGENTS.md 규칙을 읽고 START_HERE.md의 preview 실습을 실행해줘. fixed와 recursive의 경계·검색 후보·전달 문맥을 비교해줘. 모델/API/Drive 호출·모델 다운로드·서버 시작은 하지 마. 기존 규칙과 파일은 보존해줘.

Claude Code 요청:

> 현재 폴더와 상위 CLAUDE.md/AGENTS.md 규칙을 읽고 같은 rag-lab preview 명령을 실행해줘. 청크 크기 한 변수만 바꾼 새 결과를 만들고 차이를 설명해줘. 미측정 품질을 성공으로 표시하지 말고 실제 모델/API/Drive 호출은 하지 마.
