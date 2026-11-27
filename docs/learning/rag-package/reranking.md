# 같은 후보로 리랭커 비교하기

실제 공개 모델의 후속 검증은 [S1 실험 안내](live-retrieval-s1.md)에서 확인합니다. 아래 원래 구현 단계의 tiny/fake 시험 범위와 실제 실행 결과를 구분합니다.
검색은 관련 청크를 넓게 찾고, 리랭커는 이미 찾은 후보의 순서를 다시 정합니다. 예를 들어 생일 휴가 질문에서 후보가 `[포인트, 신청, 자격]`이면 자격을 앞으로 옮길 수 있습니다. 후보에 자격 청크가 없다면 리랭커로 복구할 수 없습니다. 먼저 후보 N의 회수율을 보고, 그다음 K개 선택과 문자 예산을 확인하세요.

`none`은 원래 순위를 유지합니다. CrossEncoder는 질문과 후보 본문을 한 쌍으로 읽어 단일 raw logit을 계산합니다. 음수도 정상이며 확률이 아닙니다. 서로 다른 모델의 raw score를 더하거나 절댓값으로 품질을 비교하지 않습니다. 순위·정답 회수율과 비용으로 비교하세요. 동점은 원래 순위, 청크 ID 순으로 결정합니다.

현재 지원 모델은 `BAAI/bge-reranker-v2-m3`와 `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`입니다. 두 모델의 라이선스는 Apache-2.0입니다. Qwen instruction 리랭커는 미지원입니다. 초기 연결 시험에는 수기 점수 fixture와 무작위 tiny XLM-R를 사용했습니다. 이후 두 실제 공개 모델을 같은 가상 규정집의 10질문·고정 후보로 비교했습니다. 지표별·질문별 결과는 [S1 실험 안내](live-retrieval-s1.md)에 있으며, 일반 품질·MPS·다른 OS는 미검증입니다.

## 실행 흐름

[Hybrid 실습](hybrid.md)에서 snapshot, build, 검색 결과를 먼저 만듭니다. 검색 설정의 `candidate_k`는 고정할 N 이상이어야 합니다. `3. Hybrid RAG/`를 별도 폴더로 복사하면 아래 명령을 사용할 수 있습니다.

```sh
rag-lab candidates --build .rag-runs/bm25 --result .rag-runs/answer --question-id q1 --n 20 --out .rag-runs/candidates
rag-lab rerank --candidates .rag-runs/candidates --method none --top-k 5 --context-budget-chars 4000 --out .rag-runs/none
rag-lab rerank --candidates .rag-runs/candidates --method cross-encoder --profile bge-reranker.json --top-k 5 --context-budget-chars 4000 --out .rag-runs/reranker-preview
rag-lab rerank-compare --candidates-set rerank-candidates.json --variants rerank-variants.json --out .rag-runs/rerank-comparison
rag-lab rerank-report --run .rag-runs/rerank-comparison --out .rag-runs/rerank-report
rag-lab answer-from-rerank --run .rag-runs/none --llm-config llm-local.json --out .rag-runs/answer-preview
```

이 예시의 CrossEncoder 설정은 placeholder여서 점수와 순위를 만들지 않습니다. `none`은 모델 없이 완료되며 답변은 생성 미리보기입니다. 보고서는 저장된 결과를 검증하고 지표를 다시 계산합니다. 모델·SDK·키가 없어도 재생할 수 있습니다. 산출물은 덮어쓰지 않으므로 다음 실험에는 새 출력 경로를 사용하세요.

모델 계산은 준비된 실제 profile과 `--execute-reranking`이 모두 필요합니다. 생성은 별도로 `answer-from-rerank --execute`를 사용합니다. 리랭커 preview/실패 결과에서는 생성하지 않습니다. 완성된 결과의 선택 문맥만 전달하며 검색·임베딩·리랭킹을 반복하지 않습니다. 문맥이 비면 생성 요청 없이 답변을 보류합니다.

## 로컬 모델 준비

[Hybrid 모델 준비](hybrid.md)의 격리 SDK 설치와 정확 hash lock을 사용합니다. P020은 P010의 SDK 버전을 그대로 사용하며 버전이 다르면 실행을 거부합니다. 라이브 실행은 별도 승인·준비 대상이며 이 실습은 가중치를 자동 다운로드하지 않습니다.

사용자가 준비한 Transformers XLMRobertaForSequenceClassification export를 로컬에 둡니다. `num_labels=1`인 실제 분류 head와 safetensors가 필요합니다. head를 임의 생성해 맞추지 않습니다. symlink·pickle·custom code·외부 파일 참조를 허용하지 않습니다. ST의 임의 `modules.json`도 이 경로에서 로드하지 않습니다.

예시 profile의 `revision`을 실제 HF commit 40자리, `local_path`를 로컬 export 경로, `file_manifest`를 모든 regular 파일의 SHA256으로 바꿉니다. `EXAMPLE_` 경로·0 revision·빈 manifest는 preview 전용입니다. `device=cpu`, `dtype=float32`, `max_pair_tokens=512`, `batch_size=1`, `timeout_seconds=120`이 기본값입니다. BGE는 최대8192, mMiniLM은 최대512이며 실제 tokenizer/model 한도도 충족해야 합니다.

질문+본문+special tokens가 한도를 넘으면 초과 후보 ID와 함께 질문 전체가 실패합니다. 조용히 자르거나 후보를 빼지 않습니다. 질문을 줄이거나 더 작은 청크로 별도 검색 실험을 만들어 새 후보를 고정하세요. 같은 후보 비교 중에는 청크를 바꾸지 않습니다.

## 어떤 지표를 볼까

| 지표 | 확인하는 것 |
| --- | --- |
| 후보 N Recall | 검색 단계에서 정답 청크를 확보했는가 |
| Precision@K | K개 중 관련 청크 비율. 분모는 K |
| Recall@K | 전체 관련 청크 중 K개로 회수한 비율 |
| MRR | 첫 관련 청크의 순위. 여러 조건의 완전성은 보장하지 않음 |
| nDCG@K | 관련성 등급과 순위를 함께 평가 |
| 문맥 Recall | 문자 예산 후 실제 전달한 청크의 회수율 |
| fact_recall / all_required | 여러 필수 근거의 일부/전부가 전달됐는가 |

예를 들어 전체 정답이 a·b·d이고 후보가 a·c·b라면 후보 Recall은 2/3입니다. 리랭커가 a·b·c로 바꿔도 d는 회수할 수 없습니다. K=2일 때 Recall은 1/3에서 2/3으로 바뀝니다. d는 계속 분모에 남습니다. 예산 때문에 b가 빠지면 실제 문맥 Recall은 다시 낮아집니다.

qrels는 질문별 청크 관련성 0/1/2 라벨입니다. `judgments_complete=true`일 때만 미기재 청크를 0으로 봅니다. 미완전 라벨은 N/A입니다. 정답 청크가 없는 질문의 Recall/MRR/nDCG도 N/A이며, Precision은 별도 no-answer 그룹에 집계합니다. 실패·미실행 행을 지우지 않으며 paired 변화는 양쪽 유효 질문만 계산하고 유효/전체 수를 함께 표시합니다.

facts는 필수 정보에 대응하는 canonical 원문의 `[start,end)` 구간입니다. 같은 alternative의 spans는 모두 필요(AND)하고, 여러 alternatives 중 하나만 충족해도 됩니다(OR). 같은 문서 안에서 여러 청크가 연결되어 구간 전체를 덮으면 충족됩니다. 중복 청크를 더해도 점수는 늘지 않습니다. 문자 위치는 NFC/LF 정규화 후 Unicode codepoint 기준입니다. fact macro(질문별 평균)와 micro(전체 충족 fact/전체 fact)는 분모가 다릅니다. 필수 fact가 없는 질문은 두 분모에서 제외합니다.

`--qrels`와 `--facts`는 비교할 전체 질문 세트의 hash와 source/chunk identity가 일치해야 합니다. 파일 구조는 P020 계약의 strict v1을 따릅니다. 정답 라벨은 worker에 전달하지 않습니다. Faithfulness·Correctness 평가기는 미연결이며 검색 회수율이 높다고 답변이 완전하다고 단정하지 않습니다.

## 화면과 비용

```sh
rag-lab serve --workspace . --sources sources.json --llm-config llm-local.json --reranker-config bge-reranker.json --reranker-config mmini-reranker.json
```

화면 06에서 현재 검색 결과를 고정하고, 후보와 모델을 선택해 none 대비 비교합니다. 실제 계산을 준비한 서버만 `--allow-reranking-execution`으로 시작한 뒤 화면의 별도 체크를 켭니다. qrels/facts는 서버 시작 시 `--qrels 파일 --facts 파일`로 사전 등록하고 화면에서는 등록 ID만 선택합니다. 원문·전후 순위·예산 제외와 선택 결과의 답변 미리보기를 확인하세요.

한 번에 worker 하나만 실행합니다. 각 요청은 새 worker이므로 모델 load 시간과 score 시간을 따로 봅니다. 과거 검색 지연과 새 리랭킹 지연을 같은 시점의 warm benchmark로 비교하지 않습니다. 요청 pair 수, 실제 worker 시작 수, 계산 완료 pair 수를 구분하며 timeout처럼 완료량을 모르면 null로 남깁니다. OS peak RSS는 프로세스 전체 최대치로 import/load를 포함하고 주기 샘플링 값이 아닙니다. 자동 재시도는 없습니다.
