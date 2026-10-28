# Naive RAG — Direct / LangChain 비교 후보

P011 후보 폴더다. 원본은 저장소의 `1. Naive RAG/`에 보존했다. 이 폴더의 `scripts/rag.py`와 검색·모델 경계는 기준 커밋 `58e8eb793b95c524c256c0206e37aa15ff99c6ff`의 동일 사본이다. `scripts/rag_langchain.py`는 검색→불변 문맥/메시지→무문맥 분기 또는 생성 1회→검증/원문 조립을 실제 Runnable 단계로 연결한다. 부모 소스를 import하지 않는다.

## 실행

현재 Mac에는 후보의 `.venv`와 두 색인이 준비돼 있다. 기존 단계가 소유하는 고정 Ollama 서비스(127.0.0.1:11434)를 직렬 공유한다. 원래 UI는8000, 후보 UI는8001이다. 새 UI를 실행해도 다른 포트의 프로세스를 종료하지 않는다.

```sh
.venv/bin/python scripts/serve_compare.py --port 8001
.venv/bin/python scripts/ask_compare.py --implementation langchain --retriever dense --question '생일 휴가의 자격과 신청 기한, 사용 기간을 함께 알려 주세요.'
.venv/bin/python scripts/ask_compare.py --implementation direct --retriever bm25 --question '재택근무일과 휴가일에도 사무실 식대가 나오나요?'
```

`http://127.0.0.1:8001/`에서 구현 선택 또는 두 구현 비교를 실행한다. 기본 선택은 항상 direct다. 정식 판정은 화면에 별도로 표시하며 선택을 자동 변경하지 않는다. 비교는 같은 서버 잠금 안에서 Direct→LangChain 두 질의를 직렬 실행한다. 각 결과·실패·검색/전달/제외 근거·시간·JSON을 남긴다. 수동 한 쌍의 시간으로 정식 벤치마크를 대체하지 않는다.

PDF corpus는 CLI로 명시한다. UI 기본 corpus는15개 청크이며 임의 파일 경로 입력은 받지 않는다.

```sh
.venv/bin/python scripts/ask_compare.py --implementation langchain --retriever dense --chunks data/source-v2/fixed-400-80/chunks.jsonl --index-dir .runtime/index-source-v2-fixed-400-80 --question '미사용 연차는 며칠까지 이월하고 언제까지 써야 하나요?'
```

기존 CLI `scripts/ask.py`와 API 함수 `rag.ask`는 direct 그대로다. 비교 API `POST /api/ask`는 기존 인자에 `implementation: direct|langchain`만 추가한다. `POST /api/compare`는 같은 설정의 두 결과와 pair ID/순서/시간을 반환한다. 잘못된 구현 값은400, provider502, timeout504, 기타 실행500이며 비교 한쪽 오류는 결과 배열에 유지한다. 한 비교가 두 번의 개별 질의이며, 각 질의는 무문맥0회/그 외 최대1회 생성한다.

## 독립 환경 재현

Python3.12.14와 macOS arm64 배포 hash를 고정했다. 다른 플랫폼은 동일 hash wheel 가용성을 별도로 검토해야 한다. `.venv`, `.runtime`, 모델 가중치는 Git에 없다.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-langchain.lock -r ingestion-requirements.lock
```

설치 후 기존 `runtime-lock.json`과 `generation-lock.json`을 변경하지 않는다. LangChain lock은 추가 의존성을 고정하고 기존20개 pin을 그대로 포함한다. PDF reader는 별도 ingestion lock에 있다. LangSmith 추적은 꺼져 있으며 외부 trace 전송을 사용하지 않는다.

같은 기기에서 기존 고정 모델 서비스를 재사용할 수 있다. 다음 명령은 사용자가 지정한 원본 runtime의 색인을 Qdrant의 배타적 잠금을 획득한 상태에서 새 경로로 복사하고 ID/벡터/payload/settings hash를 대조한다. 잠겨 있으면 실패하며 lock을 삭제하거나 재임베딩하지 않는다. 대상이 이미 있으면 덮어쓰지 않는다.

```sh
.venv/bin/python scripts/copy_indexes.py --source-runtime '/absolute/path/to/original/.runtime'
```

모델 서비스까지 없는 새 컴퓨터에서는 복사된 `scripts/setup_runtime.py`, `scripts/setup_generation.py`의 고정 설치 절차를 사용한다. 새로운 임베딩으로 구축한 색인은 이번 동일벡터 비교의 재현과 구분한다. 모델 이름만 같아도 충분하지 않으며 digest/runtime/template/options가 lock과 맞아야 한다.

## 검증과 관찰

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m unittest discover -s tests_langchain
```

추가 matrix 검사는 두 비교 색인이 필요하다. `copy-manifest.json`은 최초 복사와 현재 hash를 기록한다. `adoption-decision.json`은 정식 판정 사본이며, 전체 protocol/120 warm+18 cold 원응답/의미 검토/시간/실패 증거는 저장소의 `docs/verification/p011/`에 있다. 제품 사본은 그 증거 폴더를 런타임에 읽지 않는다.

[학습 가이드](LEARNING_GUIDE.md)를 따라 검색 동일성, 답변의 조건 누락, 인용 지지, 로드 시간을 별도로 관찰한다. 후속 Hybrid 구현은 P010 준비 검토와 채택 후 진행한다.
