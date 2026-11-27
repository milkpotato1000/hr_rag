# 최신 패키지 설치와 모델 준비

실제 공개 모델의 후속 검증은 [S1 실험 안내](live-retrieval-s1.md)에서 확인합니다. 아래 원래 구현 단계의 tiny/fake 시험 범위와 실제 실행 결과를 구분합니다.
현재 dev 패키지는 규칙·의미·LLM 청킹, BM25/Dense/Hybrid, 고정 후보 리랭커와 모델 준비 CLI를 제공합니다. [P028 설치 문서](install.md)의 고정 SHA는 과거 기준선입니다. 최신 검증 소스와 배포물 hash는 [P031 검증 기록](../../verification/p031/README.md)에서 확인합니다. main 승격·PyPI 게시를 뜻하지 않습니다.

지원 Python 3.10 이상과 새 환경을 사용합니다. 아래는 기존 환경을 바꾸지 않는 설치 예시입니다. `git rev-parse HEAD`의 SHA를 실험 기록에 보관하세요. 검증 기록의 소스를 재현할 때는 그 기록의 구현 SHA를 checkout합니다.

```sh
git clone --branch dev https://github.com/milkpotato1000/hr_rag.git rag-lab-source
cd rag-lab-source
git rev-parse HEAD
python3 -m venv .rag-runs/build-env
.rag-runs/build-env/bin/python -m pip install --require-hashes -r packaging/requirements-build.lock
.rag-runs/build-env/bin/python -m build --no-isolation --outdir .rag-runs/dist
python3 -m venv /원하는/새환경
/원하는/새환경/bin/python -m pip install /배포물/milkpotato_rag_lab-0.1.0.dev1-py3-none-any.whl
/원하는/새환경/bin/rag-lab init --out /원하는/새실습폴더
```

wheel은 source 없는 작업 폴더에서도 동작합니다. core-only에서 catalog·고정 계획·LLM 설정·BM25 preview를 시작할 수 있습니다. 공개 모델 파일 준비/변환/추론에는 package의 `requirements-retrieval.lock`이 지정한 SDK가 필요합니다. PDF·Drive는 별도 lock입니다. 새 환경에서 다음처럼 설치합니다.

```sh
/원하는/새환경/bin/python -m pip install --require-hashes -r rag_package/requirements-retrieval.lock
```

이 명령은 clone 안의 lock을 읽는 예시입니다. source 없는 설치에서는 다음 명령이 설치된 package 안의 lock 경로를 반환합니다.

```sh
/원하는/새환경/bin/python -c 'from importlib.resources import files; print(files("rag_package").joinpath("requirements-retrieval.lock"))'
```

출력된 절대경로를 같은 환경의 `python -m pip install --require-hashes -r /출력된/requirements-retrieval.lock`에 사용합니다. 환경 변수·내부 registry를 변경하지 않습니다. `[retrieval]`/`[all]` extras도 제공하지만 엄밀한 전이 의존성 재현에는 hash lock을 사용하세요. SDK 설치와 모델 가중치 다운로드는 별개입니다. 기존 전역 환경을 업그레이드할 필요가 없습니다.

새 실습 폴더에서 START_HERE.md와 [모델 준비 안내](model-preparation.md)를 읽고 아래 순서로 진행합니다.

1. 오프라인 catalog → 고정 plan → prepare preview.
2. 파일 다운로드 또는 검증된 원본 import를 명시. BGE-M3는 tensor-only 변환도 명시.
3. 생성 profile의 `model-check`, local/API/mixed LLM 설정, 역할별 `doctor`.
4. 기존 설정의 profile 참조와 serve 등록 인자로 연결. preview로 문맥 확인 후 별도 명시 추론.

샘플 local 설정은 실제 identity 확인 전 실행을 차단합니다. API 설정 생성은 키를 읽지 않으며 서버 이용권을 검증하지 않습니다. 준비 완료와 품질 통과를 구분합니다. 코딩 도구 요청 예시도 [모델 준비 안내](model-preparation.md)에 있습니다.

설치 시험은 같은 Mac의 독립 venv와 source 없는 cwd에서 수행하며 다른 OS/컴퓨터, Codex와 Claude Code 양쪽 제품 UI, 실제 사전학습 모델·유료 API 성공으로 확대하지 않습니다. 평가기 실험 보류와 기존 파일 선택창 검증 차단 상태는 유지됩니다.
