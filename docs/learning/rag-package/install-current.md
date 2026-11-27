# 최신 패키지 설치와 모델 준비

[학습 시작점](README.md)에서 이어지는 현재 dev 설치 경로입니다. 규칙·의미·LLM 청킹, BM25/Dense/Hybrid, 선택 리랭커와 모델 준비 CLI를 제공합니다. [S2c 설치 기록](../../verification/p032-s2c/README.md)에 새 문서 배포물 hash와 core-only 검증을 기록했습니다. [P028](install.md)·[P031](../../verification/p031/README.md) 설치 기록은 당시 기준선입니다. 실제 [S1](live-retrieval-s1.md)·[S2b](chunk-comparison-live.md) 실험의 이전 wheel은 보존하며 새 문서 wheel로 재실험했다고 표시하지 않습니다. main 승격·PyPI 게시가 아닙니다.

Python 3.10 이상, macOS/Linux 파일 저장 기능을 사용합니다. 아래는 비어 있는 작업 위치에서 실행하는 설치 예시입니다. 이미 같은 이름의 폴더가 있으면 다른 새 이름을 사용하세요. clone의 SHA를 기록하고 재현할 때는 검증 기록의 소스 SHA를 사용합니다. 빌드 도구 설치는 네트워크를 사용하지만 모델은 다운로드하지 않습니다.

```sh
git clone --branch dev https://github.com/milkpotato1000/hr_rag.git rag-lab-source
cd rag-lab-source
git rev-parse HEAD
python3 -m venv .rag-runs/build-env
.rag-runs/build-env/bin/python -m pip install --require-hashes -r packaging/requirements-build.lock
.rag-runs/build-env/bin/python -m build --no-isolation --outdir .rag-runs/dist
rag_lab_wheel="$PWD/.rag-runs/dist/milkpotato_rag_lab-0.1.0.dev1-py3-none-any.whl"
cd ..
python3 -m venv rag-lab-env
rag_lab_python="$PWD/rag-lab-env/bin/python"
rag_lab_cli="$PWD/rag-lab-env/bin/rag-lab"
"$rag_lab_python" -m pip install --no-deps "$rag_lab_wheel"
"$rag_lab_cli" init --out rag-lab-practice
cd rag-lab-practice
"$rag_lab_cli" doctor --config fixed.json
```

doctor의 exit 3/`needs_configuration`은 미설정 샘플 모델의 예상 상태입니다. 생성된 `START_HERE.md`를 읽으세요. 이후 예시의 `rag-lab`을 그대로 쓰려면 새 환경의 bin을 PATH에 추가하거나 위 `"$rag_lab_cli"` 절대경로 변수를 사용합니다. 설치 소스 폴더와 실습 폴더는 독립이며 하네스를 설치할 필요가 없습니다.

wheel은 source 없는 작업 폴더에서도 동작합니다. core-only에서 catalog·고정 계획·LLM 설정·BM25 preview를 시작할 수 있습니다. 공개 모델 파일 준비/변환/추론에는 package의 `requirements-retrieval.lock`이 지정한 SDK가 필요합니다. PDF·Drive는 별도 lock입니다. 필요한 단계에 도달했을 때만 선택 의존성을 설치합니다. source 없는 실습 폴더에서도 다음처럼 설치된 package의 lock을 찾을 수 있습니다.

```sh
rag_lab_retrieval_lock=$("$rag_lab_python" -c 'from importlib.resources import files; print(files("rag_package").joinpath("requirements-retrieval.lock"))')
"$rag_lab_python" -m pip install --require-hashes -r "$rag_lab_retrieval_lock"
```

이 선택 설치는 이번 core-only 검증에서 실행하지 않았습니다. 환경 변수·내부 registry를 변경하지 않습니다. `[retrieval]`/`[all]` extras도 제공하지만 엄밀한 전이 의존성 재현에는 hash lock을 사용하세요. SDK 설치와 모델 가중치 다운로드는 별개입니다. 기존 전역 환경을 업그레이드할 필요가 없습니다.

새 실습 폴더에서 START_HERE.md와 [모델 준비 안내](model-preparation.md)를 읽고 아래 순서로 진행합니다.

1. 오프라인 catalog → 고정 plan → prepare preview.
2. 파일 다운로드 또는 검증된 원본 import를 명시. BGE-M3는 tensor-only 변환도 명시.
3. 생성 profile의 `model-check`, local/API/mixed LLM 설정, 역할별 `doctor`.
4. 기존 설정의 profile 참조와 serve 등록 인자로 연결. preview로 문맥 확인 후 별도 명시 추론.

샘플 local 설정은 실제 identity 확인 전 실행을 차단합니다. API 설정 생성은 키를 읽지 않으며 서버 이용권을 검증하지 않습니다. 준비 완료와 품질 통과를 구분합니다. 코딩 도구 요청 예시도 [모델 준비 안내](model-preparation.md)에 있습니다.

이번 설치 시험은 같은 Mac의 독립 core-only venv와 source 없는 cwd에서 모델 없이 수행했습니다. 다른 OS/컴퓨터나 두 코딩 제품 UI, 실제 생성·API·Drive 성공을 뜻하지 않습니다. 실제 검색·리랭커의 제한된 관측은 위 S1/S2b 기록을 별도로 참고하세요. 평가기 실험 보류와 기존 파일 선택창 검증 차단 상태는 유지됩니다.
