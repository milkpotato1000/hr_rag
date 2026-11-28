# HR 규정집으로 배우는 RAG

## Codex 또는 Claude Code로 첫 검색하기

공개 dev 소스를 내려받고 그 폴더를 사용하는 코딩 도구에서 여세요.

```sh
git clone --branch dev https://github.com/milkpotato1000/hr_rag.git rag-lab-source
cd rag-lab-source
```

**Codex에 줄 요청**

> 현재 dev 소스 폴더에서 Python 3.11 이상을 찾아 scripts/first_handbook.py를 실행해 줘. --out은 옆의 새 폴더 "../rag-lab-first"로 하고 이미 있으면 새 이름을 써 줘. first-run.json에서 설치와 검색 상태를 확인하고, 생일 특별휴가 신청 기한을 찾은 전달 청크의 순위·PDF 쪽·조항·원문을 보여 줘. 모델 호출은 하지 마.

**Claude Code에 줄 요청**

> 현재 dev 소스 폴더에서 Python 3.11 이상을 찾아 scripts/first_handbook.py를 실행해 줘. --out은 옆의 새 폴더 "../rag-lab-first"로 하고 이미 있으면 새 이름을 써 줘. first-run.json에서 설치와 검색 상태를 확인하고, 생일 특별휴가 신청 기한을 찾은 전달 청크의 순위·PDF 쪽·조항·원문을 보여 줘. 모델 호출은 하지 마.

두 도구가 실행할 명령은 같습니다. macOS/Linux에서 아래 python3은 3.11 이상이어야 합니다. 고정된 빌드 도구와 PDF 리더는 새 가상환경에 설치됩니다. 오프라인 wheel이 준비된 경우 `--wheelhouse "/경로/wheels"`를 추가하세요.

```sh
python3 scripts/first_handbook.py --out "../rag-lab-first"
```

새 폴더의 `first-run.json`에 소스 SHA, 설치한 wheel의 해시, 검색 근거가 기록됩니다. `practice/evidence/result.json`에서 전달 청크 전문을 읽을 수 있습니다. 중간 실패 시 `failed_stage`와 `commands.log`의 마지막 명령을 확인하고 원인을 수정한 뒤 새 이름으로 다시 시작하세요. 기존 수동 설치 절차도 사용할 수 있습니다. [수동 설치](docs/learning/rag-package/install-current.md)

### 준비된 로컬 Qwen으로 첫 답변 받기

첫 검색을 완료했고 로컬 Ollama에 실습 모델 qwen3:4b가 준비돼 있다면, 소스 폴더에서 다음 명령을 실행하세요. 첫 실습 출력 이름을 바꿨다면 그 폴더 이름을 사용하세요.

```sh
cd "../rag-lab-first/practice"
../env/bin/rag-lab first-answer --execute
```

터미널과 `first-answer/answer/result.json`에서 답변, 인용한 PDF 쪽, 조항 원문을 확인하세요. `first-answer` 폴더가 이미 있으면 저장된 결과를 읽으세요. 모델이 준비되지 않은 경우에는 출력의 action을 확인하세요. [설치본의 첫 답변과 PDF 인용 대조](docs/verification/p032-s25/README.md)

**Codex와 Claude Code에 줄 요청**

> 첫 검색을 마친 practice 폴더에서 준비된 로컬 Qwen으로 같은 질문에 한 번 답해 줘. 기존 BM25 인덱스를 재사용하고 인용한 PDF 쪽과 신청 기한 원문을 대조해 줘. 이전 답이 저장돼 있으면 그 결과를 읽어 줘.

다른 모델이나 검색 방식을 선택하려면 소스 폴더에서 다음 절차를 시작하세요.

```sh
cd "../rag-lab-first/practice"
. ../env/bin/activate
rag-lab generation-setup --provider ollama --model qwen3:4b --out my-local
rag-lab pipeline-setup --llm-config my-local/model.json --chunk-config chunk-fixed.json --method bm25 --out my-search
```

준비된 로컬 모델의 실답변, 선택 API 설정, 청킹·Hybrid·리랭커 설정과 내 PDF 선택은 실습 폴더의 HANDBOOK.md에 이어집니다. [모델 설정](docs/verification/p032-s14/README.md) · [검색과 리랭커 선택](docs/verification/p032-s15/README.md) · [내 문서와 질문](docs/verification/p032-s16/README.md)

[현재 dev 설치 안내](docs/learning/rag-package/install-current.md)를 따라 wheel을 설치하고 새 실습 폴더를 만드세요. 폴더 안의 [HANDBOOK.md](rag_package/resources/sample/HANDBOOK.md)에서 기본 예제 PDF로 **“생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?”**를 검색합니다. PDF 1쪽 BD-03과 전달 청크를 직접 대조한 뒤 로컬 Qwen 4B로 답변과 인용을 확인할 수 있습니다.

[학습 목차](docs/learning/rag-package/README.md) · [설치본 첫 검색 검증](docs/verification/p032-s10/README.md) · [로컬 모델의 실제 답변](docs/verification/p032-s8/README.md) · [학습 UI 재생](docs/verification/p032-s9/README.md)

## 이전 단계 재현

LangChain 비교 서버는 `1. Naive RAG/variants/langchain/`에서 `.venv/bin/python scripts/serve_compare.py --port 8001`을 실행한다. **실험 → 구현 비교**는 http://127.0.0.1:8001/experiments/implementation 이다.


HR 규정 문서에 근거해 질문에 답하고, 근거가 부족하면 담당자에게 연결하는 RAG 에이전트 프로젝트입니다.
기획·개발은 linked Git worktree로 분리하며 첫 구현은 합성 HR 데이터와 로컬 검색 평가 CLI입니다.

## 작업 위치

코덱스에서는 상위 `hr_rag/` 하나를 프로젝트로 엽니다. 그 안에 아래 세 작업폴더를 둡니다.
상위 폴더에는 `.git`을 두지 않으며, Git과 프로젝트 스크립트는 해당 하위 폴더에서 실행합니다.
표의 경로는 각 하위 작업폴더 기준입니다.

| 폴더 | 브랜치 | 역할 |
| --- | --- | --- |
| `../hr_rag_main` | `main` | 릴리스 기준. 명시적 승격 요청 시에만 변경 |
| `../hr_rag_plan` | `plan` | 요구사항, 계약, P번호 작업 기획 및 준비 검토 |
| `../hr_rag_dev` | `dev` | 채택한 계획 구현, 검증, 실행 로그 |

세 폴더는 하나의 Git 저장소를 공유하는 linked worktree입니다.
개인 공개 저장소는 <https://github.com/milkpotato1000/hr_rag>이며 원격 이름은 `personal`입니다.
plan/dev만 게시하며 main의 push와 승격은 별도 명시 요청이 필요합니다.

## 시작하기

상위 프로젝트에서 “기획해줘”는 `hr_rag_plan/`, “구현해줘”·“검증해줘”·“다음 큐 진행해줘”는
`hr_rag_dev/`를 사용합니다. 양쪽 작업은 plan 준비 검토 → dev 통합·정확한 채택 순서로 진행합니다.
각 작업폴더의 AGENTS.md와 기존 P카드·검증·Git 규칙을 따릅니다.

plan/dev 채팅을 별도로 만들 때에도 같은 상위 프로젝트를 사용합니다. 각 채팅의 초기 지시에 역할과
작업폴더를 고정하므로 “다음 작업”을 요청하면 해당 역할로 이어갑니다. 새 채팅은 최초 규칙·상태·큐를
읽기 전용으로 확인하고 다음 요청을 기다립니다. 기존 채팅이 있으면 새 채팅 제목에 구분 표시를 붙입니다.

새 컴퓨터에서 같은 폴더 구조를 만든 뒤, 상위 `hr_rag/`에서 다음 명령으로 진입 규칙을 복원합니다.

```sh
cp hr_rag_plan/docs/process/workspace-AGENTS.md AGENTS.md
```

진입 규칙 원본은 Git으로 관리하고, 상위 사본은 로컬에서 사용합니다. 기존 상위 규칙이 있다면 내용을 통합합니다.


- plan 폴더에서 “다음 작업 기획해줘”와 제품 목표를 요청합니다.
- dev 폴더에서 “다음 큐 진행해줘”를 요청합니다.
- 큐 조회: `python3 scripts/work_queue.py --owner all`
- 개발 계약 확인: `python3 scripts/contract_guard.py check`

[프로젝트 기획](docs/planning/project-brief.md)과 [아키텍처 방향](docs/architecture/system-design.md)을 확인합니다.
첫 구현 계약은 [P001 합성 HR 문서와 검색 평가 기반](docs/planning/plans/P001.md)입니다. 최신 실행 상태는 P카드와 큐에서 확인합니다.
plan 또는 dev 폴더에서 [작업 흐름](docs/process/work-queue.md)을 따릅니다.

## 계약과 증거

`docs/planning/`, `docs/architecture/`, `config/semantics/`와 하네스 규칙은 plan이 관리합니다.
필요한 문서는 첫 기획 시 작성합니다. dev는 정확한 plan 커밋을 채택한 뒤 구현하며,
P카드의 실행 상태·체크 표시·추가 로그만 수정합니다.
검증 근거는 `docs/verification/` 또는 `docs/progress/`에 커밋합니다.

새 clone에서는 plan/dev 브랜치를 가져오고 작업 폴더를 준비한 뒤,
dev에서 `python3 scripts/contract_guard.py install`로 로컬 훅을 설치합니다.
채택 기록은 `.harness/adopted-plan.json`에서 확인합니다.
로컬 훅은 실수 방지용이며 서버의 접근 통제는 아닙니다.

공개 저장소에 비밀키·토큰·개인 인사 데이터·비공개 문서를 커밋하지 않습니다.

## 현재 제품 실행 위치

원문 파일 위치는 [원문 Markdown·PDF 안내](<1. Naive RAG/data/source-v2/README.md>)에서 확인합니다.
현재 화면의 기본 입력은 [기존 수작성 청크 15개](<1. Naive RAG/data/synthetic/chunks.jsonl>)이며,
원문 v2에서 추출·분할한 [청크 20개](<1. Naive RAG/data/source-v2/fixed-400-80/chunks.jsonl>)는 별도 데이터입니다.

평가 기반·BM25·실제 로컬 Dense 검색은 큰 단계 [1. Naive RAG](<1. Naive RAG/README.md>) 안에 모았습니다.
P번호마다 새 번호 폴더를 만들지 않습니다. 답변 생성도 같은 큰 단계에서 실행합니다.
현재 구현 범위는 P001 평가 기반, P002 BM25, P003 로컬 Dense, P004 실제 Qwen 답변·인용·보류입니다. P005 한국어 질문 화면·학습 가이드, P006 원문 추출·청킹, P009 근거 ID 선택·코드 원문 인용까지 연결했습니다.

```sh
cd '1. Naive RAG'
python3 -m unittest discover -s tests -v
python3 scripts/run_bm25_baseline.py \
  --chunks data/synthetic/chunks.jsonl \
  --queries data/synthetic/queries.jsonl \
  --top-k 20 --k 5 10 20 \
  --output-dir /tmp/hr-rag-bm25-new
```

Python 3.9 이상과 표준 라이브러리만 사용합니다. 결과 부모 폴더는 존재해야 하고 결과 경로는 새 경로여야 합니다.
데이터 스키마·지표·실패 정책과 독립 실행 방법은 단계 README를 따릅니다.
실제 기준선·출처·단독 복사 실행·회귀 결과는 [P002 검증 기록](docs/verification/p002/README.md)에 있습니다.

원래 루트 scripts/evaluate_retrieval.py, tests와 data/synthetic은 과거 P001 계약 재현용으로 보존합니다.
루트에서 `python3 -m unittest discover -s tests -v`로 과거 회귀를 실행할 수 있습니다.
새 기능은 큰 단계 폴더에서 개발합니다. 기존 [P001 검증 기록](docs/verification/p001/README.md)은 원래 실행 위치·이력 그대로 유지합니다.
계약 검사와 큐 조회는 저장소 루트에서 실행합니다.

로컬 Dense 환경·실행/정지와 이번 학습 포인트는 [큰 단계 README](<1. Naive RAG/README.md>)의 P003 절에 있습니다.
실제 모델·영속 재open·53개 테스트·검색 비교는 [P003 검증 기록](docs/verification/p003/README.md)을 참고합니다.
전체 순서는 [Naive RAG 구현·학습 로드맵](docs/planning/naive-rag-roadmap.md)을 따릅니다.


## 학습 UI 실행

```sh
cd '1. Naive RAG'
.venv/bin/python scripts/runtime.py start
.venv/bin/python scripts/serve.py --port 8000
```

http://127.0.0.1:8000 에서 검색→문맥→답변·인용·보류를 관찰합니다.
[학습 가이드](<1. Naive RAG/LEARNING_GUIDE.md>)는 구현 숙제 대신 예상·실패 분류·한 변수 실험·평가 해석을 안내합니다.
종료는 UI 터미널 Ctrl+C와 `.venv/bin/python scripts/runtime.py stop`입니다.
실제 답변의 조건 누락/과도보류가 남아 있으며 [P004 의미 검토](docs/verification/p004/final-review.md)와 [P005 검증](docs/verification/p005/README.md)에 공개합니다.

범용 패키지의 [Hybrid 검색 실습](docs/learning/rag-package/hybrid.md)과 [3. Hybrid RAG](<3. Hybrid RAG/README.md>)는 BM25/Dense/RRF를 비교합니다. 실제 한국어 모델 품질·평가기 실험은 별도 후속입니다.
