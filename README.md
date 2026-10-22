# hr_rag

HR 규정 문서에 근거해 질문에 답하고, 근거가 부족하면 담당자에게 연결하는 RAG 에이전트 프로젝트입니다.
기획·개발은 linked Git worktree로 분리하며 첫 구현은 합성 HR 데이터와 로컬 검색 평가 CLI입니다.

## 작업 위치

| 폴더 | 브랜치 | 역할 |
| --- | --- | --- |
| `hr_rag` | `main` | 릴리스 기준. 명시적 승격 요청 시에만 변경 |
| `../hr_rag-plan` | `plan` | 요구사항, 계약, P번호 작업 기획 및 준비 검토 |
| `../hr_rag-dev` | `dev` | 채택한 계획 구현, 검증, 실행 로그 |

세 폴더는 하나의 Git 저장소를 공유하는 linked worktree입니다.
개인 공개 저장소는 <https://github.com/milkpotato1000/hr_rag>이며 원격 이름은 `personal`입니다.
plan/dev만 게시하며 main의 push와 승격은 별도 명시 요청이 필요합니다.

## 시작하기

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

## 로컬 검색 평가 실행

Python 3.9 이상과 표준 라이브러리만 사용합니다. 네트워크, 패키지 설치, 모델 다운로드가 필요 없습니다.
아래 명령은 dev worktree 루트에서 실행합니다.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/evaluate_retrieval.py \
  --chunks data/synthetic/chunks.jsonl \
  --queries data/synthetic/queries.jsonl \
  --rankings data/synthetic/example_rankings.jsonl \
  --k 5 10 20 \
  --output /tmp/hr-rag-evaluation.json
```

`example_rankings.jsonl`은 의도적으로 불완전한 수기 순위입니다. 실제 검색 엔진 성능을 의미하지 않습니다.
자체 순위 파일은 질문마다 `{"query_id":"q01","chunk_ids":["birthday-eligibility"]}` 같은 JSON 객체를 한 줄씩 기록합니다.
모든 질문이 정확히 한 번 포함되어야 하며, 검색 결과가 없으면 `chunk_ids: []`를 사용합니다.
데이터의 필수 필드와 등급 기준은 [합성 데이터 설명](data/synthetic/README.md)을 참고합니다.

평가기는 검증을 마친 뒤 JSON 결과 파일을 원자적으로 교체합니다. 출력 부모 폴더는 미리 존재해야 합니다.
입력 오류는 stderr와 종료 코드 2로 알리며 기존 결과를 보존하거나 새 결과를 만들지 않습니다.
출력 경로로 입력 파일 자체나 그 심볼릭 링크·하드 링크를 지정할 수 없습니다.

결과에는 `metadata`(평가기 버전, 세 입력의 SHA-256, K, 청크·질문 수와 answerable/unanswerable 분모),
`per_query`(질문별 검색 수 및 K별 지표), `macro`(answerable 질문의 단순 평균), `unanswerable`(검색 결과 유무 집계)이 포함됩니다.
같은 바이트 입력과 K에는 전체 결과 JSON도 동일합니다. 파일의 줄바꿈·공백 변경 역시 hash를 바꿉니다.

| 지표 | 계산 |
| --- | --- |
| Recall@K | top K의 등급 1 이상 청크 수 / 전체 등급 1 이상 청크 수 |
| Precision@K | top K의 등급 1 이상 청크 수 / K. 짧은 결과도 분모 K 유지 |
| MRR@K | top K 첫 relevant의 1-based 순위 역수. 없으면 0 |
| nDCG@K | gain `2**rel-1`, discount `log2(rank+1)`. 전체 qrels의 이상 순위 top K로 정규화 |

K는 양의 고유 정수입니다. 근거 없는 질문의 네 검색 지표는 null이고 macro에서 제외합니다.
answerable이 0개이면 macro도 null입니다. `unanswerable`은 질문 수, 검색 결과가 있는/빈 질문 수와 비율을 별도로 기록하고
해당 질문이 0개이면 비율은 null입니다. 이 비율은 답변 보류 정확도가 아닙니다.

실제 검증 출력·실패 이력·예시 결과는 [P001 검증 기록](docs/verification/p001/README.md)에 있습니다.
