# milkpotato-rag-lab 0.1.0.dev1

합성 문서로 PDF/TXT/MD→규칙·의미·LLM 청킹→BM25/Dense/Hybrid→선택 리랭커→선택 문맥→답변 preview를 학습하는 Python 패키지입니다. `rag_package`가 import 이름이고 `rag-lab`이 공통 CLI입니다. PyPI에 게시하지 않았습니다. 승인된 dev commit에서 만든 wheel을 로컬 설치합니다. main에 이 기능이 있다고 가정하지 마세요.

Python 3.10+ 및 macOS/Linux의 원자적 저장 primitive가 필요합니다. 실제 검증은 동일 Mac의 새 Python 3.12 venv이며 다른 OS/모든 Python 버전/두 코딩 도구 UI를 검증하지 않았습니다. Windows는 지원하지 않습니다.

## 설치와 시작

검증된 dev source commit·wheel SHA256·설치 결과는 저장소 `docs/verification/p031/`에 기록합니다 (기존 P028 기록도 보존합니다). 배포 wheel의 hash를 해당 기록과 대조하세요. 소스에서 만들 경우 그 **고정 commit**을 checkout하고 별도 build venv에 `packaging/requirements-build.lock`을 해시 검증하여 설치한 뒤 `python -m build --no-isolation`을 사용합니다. build는 sdist를 만들고 그 sdist에서 wheel을 만듭니다. build 도구 설치에는 공식 PyPI 접근이 필요합니다. 모델/API/Drive 호출과 별개입니다.

```sh
python3 -m venv /원하는/새환경
/원하는/새환경/bin/python -m pip install /배포물/milkpotato_rag_lab-0.1.0.dev1-py3-none-any.whl
/원하는/새환경/bin/rag-lab --version
/원하는/새환경/bin/rag-lab init --out /원하는/새실습폴더
```

생성한 폴더에서 START_HERE.md를 읽고 `rag-lab doctor`와 preview 실습을 진행합니다. init은 기존 경로를 덮어쓰지 않습니다. core는 표준 라이브러리만 필요합니다. PDF는 같은 wheel의 `[pdf]`, OAuth helper는 `[drive]`, 로컬 HF 임베딩·CrossEncoder는 `[retrieval]`, 전체는 `[all]` extra로 설치합니다. 정확 pin/hash는 패키지에 포함된 requirements-pdf.lock/requirements-drive.lock/requirements-retrieval.lock을 따릅니다. SDK 설치가 로그인이나 모델 실행을 시작하지 않습니다.

`doctor --config fixed.json`의 exit 3은 샘플 설정을 본인 모델 정보로 바꿔야 한다는 안내입니다. preview는 가능하며 실제 invoke는 키 조회/HTTP 전에 configuration_required로 거부합니다. `model-plan`/`model-prepare`/`model-import`로 공개 모델 파일과 profile을 준비하고, `llm-configure --spec … --out …`로 local/API/mixed 역할 설정을 만듭니다. local identity는 명시 `--inspect-local`의 tags/show로 확인합니다. 파일 hash와 digest를 수작업으로 채울 필요가 없습니다. 이후에도 doctor는 서버·키·Drive 접근을 확인하지 않습니다. optional 미설치만으로 core를 막지 않습니다.

실제 답변은 사용자가 선택 문맥 전송과 호출/비용 범위를 정하고 명시 execute할 때 요청합니다. API에 질문/문서 일부가 전송되며 비용은 미측정입니다. 키는 env 참조만, credential은 실습 폴더/Git 밖 전용0700/0600 경로에 보관합니다. 자동 재시도/모델 변경/다운로드는 없습니다. Drive 단일 파일 수집은 실제 연결 코드가 있으나 가짜 인증/HTTP만 검증했습니다. P013 보류·이전 실험 이력은 그대로입니다.

Codex와 Claude Code 모두 생성 폴더와 상위의 AGENTS.md/CLAUDE.md 규칙을 읽게 한 후 “START_HERE.md의 preview 실습을 실행하고 청크/검색/전달 문맥을 설명해줘. 모델/API/Drive 호출은 하지 마”라고 요청할 수 있습니다. init은 두 도구·Git·하네스를 설치하거나 기존 규칙을 덮어쓰지 않습니다. 이 안내는 공통 CLI 사용법이며 실제 두 제품 UI 시험 결과가 아닙니다.

Dense/Hybrid와 고정 후보 CrossEncoder·비교·보고서·선택 문맥 생성 연결 및 통합 UI를 지원합니다. 다섯 청킹 방식과 모델 파일 준비를 지원하며 실제 한국어 사전학습 품질은 미검증입니다. 평가기는 보류 상태입니다. 실행법은 저장소 docs/learning/rag-package/install-current.md, model-preparation.md, hybrid.md, reranking.md, model-chunking.md를 참고하세요. 소스 재배포 권한은 별도 확인 대상이며 이 패키지는 MIT 등 라이선스를 임의로 부여하지 않습니다. 모델 라이선스와 소스 권리는 별개입니다.
