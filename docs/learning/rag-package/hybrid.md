# BM25·Dense·Hybrid를 비교하기

실제 공개 모델의 후속 검증은 [S1 실험 안내](live-retrieval-s1.md)에서 확인합니다. 아래 원래 구현 단계의 tiny/fake 시험 범위와 실제 실행 결과를 구분합니다.
같은 문서와 청크에서 검색 방식만 바꾸어 봅니다. **BM25는 단어 일치, Dense는 임베딩의 cosine, Hybrid는 두 순위의 RRF 결합**입니다. 점수의 단위가 다르므로 BM25 점수와 cosine를 직접 더하지 않습니다. 생성·평가 LLM과 검색 임베딩은 별도 역할입니다.

[독립 실습 폴더](<../../../3. Hybrid RAG/README.md>) · [화면 안내](ui.md) · [검증과 실제 한계](../../verification/p010/README.md)

## 설치와 모델 준비

기본 패키지는 표준 라이브러리로 BM25를 실행합니다. 검색 SDK는 wheel의 `[retrieval]` extra입니다. 새 가상환경에서 검증 기록의 source로 wheel을 빌드하고 해당 wheel을 설치하세요. 정확 재현에는 [검색 의존성 lock](../../../rag_package/requirements-retrieval.lock)을 `pip install --require-hashes -r`로 먼저 설치한 뒤 wheel을 `--no-deps`로 설치합니다. 기존 venv를 업그레이드하지 않습니다. lock은 Python 3.12/macOS arm64에서 검증했으며 core의 Python 3.10 문법 지원과 모든 extra/OS 호환성은 다릅니다.

| 선택 | 차원 | 전처리 | 모델 한도 / 기본 실습 한도 |
| --- | --- | --- | --- |
| intfloat/multilingual-e5-small | 384 | 문서 `passage: `, 질문 `query: `, 평균 pooling·정규화 | 512 / 512 tokens |
| BAAI/bge-m3 | 1024 | 접두어 없음, 모델 정의 CLS pooling·정규화 | 8192 / 512 tokens |

두 모델은 MIT로 공개되어 있습니다. 전처리와 원본은 [E5 모델 카드](https://huggingface.co/intfloat/multilingual-e5-small), [BGE-M3 모델 카드](https://huggingface.co/BAAI/bge-m3)를 따릅니다. BGE의 learned sparse·multi-vector 출력은 사용하지 않습니다. Hybrid의 sparse 검색기는 BM25입니다.

예제 embedding JSON의 0 revision/빈 manifest/EXAMPLE 경로는 **미설정**입니다. 실제 모델 파일을 자동 다운로드하지 않습니다. 사용자가 별도로 검토·준비한 자체 완결 디렉터리를 등록해야 합니다. HF cache symlink를 그대로 등록하거나 프로그램이 임의로 해제하지 않습니다. 설정에는 정확한 HF ID·40자리 commit revision·설정/tokenizer/safetensors를 포함한 모든 파일의 SHA256·절대 local_path가 필요합니다. 모델 catalog와 차원·pooling이 일치해야 하며 Python/custom code/pickle 가중치는 거부합니다. 최대 100파일/4GiB입니다. GGUF/Ollama digest는 이 HF revision과 다른 값입니다.

실행은 `local_files_only=True`, `trust_remote_code=False`, `token=False`, offline 환경의 요청별 worker입니다. CPU/float32/batch1이 기본이고 MPS는 선택 설정만 지원하며 이번 검증에서 실행하지 않았습니다. 길이는 접두어·special tokens를 포함합니다. 초과 입력은 `input_too_long`과 청크 ID/query를 반환하며 자동 자르기·재청킹하지 않습니다. 크기를 줄여 새 청킹/색인을 명시적으로 만드세요.

## 호출을 구분하기

```sh
rag-lab retrieval-preview --config e5-hybrid.json
rag-lab build --snapshot .rag-runs/snapshot --config e5-hybrid.json --out .rag-runs/hybrid --execute-retrieval
rag-lab ask --run .rag-runs/hybrid --config e5-hybrid.json --question '생일 휴가 자격은?' --out .rag-runs/answer --execute-retrieval
```

첫 명령은 설정만 검사하고 실제 모델 파일·SDK를 로드하지 않습니다. `--execute-retrieval`은 문서/질문 임베딩만 허용합니다. `--execute`는 별도의 생성 LLM 호출 허용입니다. 위 명령에는 생성 허용이 없으므로 검색 근거·프롬프트를 저장하고 답변을 생성하지 않습니다. 초기 P010은 tiny 모델로 검증했고, 후속 S1에서는 E5/BGE의 실제 Dense/Hybrid 각 10문항을 비교했습니다.

같은 문서·청킹·임베딩으로 top-k/candidate-k/RRF/문맥 예산/LLM만 바꾸면 기존 문서 벡터를 사용합니다. query는 매번 새 임베딩이 필요합니다. compare 내부는 같은 색인을 복사·검증해 문서 계산을 재사용합니다. 개별 build를 새로 요청하면 새 결과를 만들므로 불필요한 build를 반복하지 마세요. 파일·전처리·SDK가 다르면 혼용하지 않고 stale 오류로 실패합니다. 색인 fingerprint는 실제 float32 vector bytes와 청크 순서, source/config/SDK identity를 포함합니다.

## 화면 실습

```sh
rag-lab serve --workspace /절대/실습폴더 --sources /절대/실습폴더/sources.json \
  --llm-config /절대/실습폴더/llm-local.json \
  --embedding-config /절대/실습폴더/e5-embedding.json \
  --embedding-config /절대/실습폴더/bge-embedding.json \
  --allow-retrieval-execution
```

먼저 snapshot을 만들고, 검색 섹션에서 방식·임베딩·candidate-k·RRF를 설정한 뒤 청크·색인을 만듭니다. Dense/Hybrid에서는 ‘로컬 임베딩 계산 허용’을 명시적으로 체크해야 합니다. 서버 flag나 실제 설정이 없으면 계산하지 않습니다. 등록 경로·키를 웹에서 편집하지 않으며 생성 실행 허용도 자동으로 켜지지 않습니다.

1. BM25 기준 결과를 저장합니다. 이 경로의 임베딩 계산은 0회입니다.
2. 청크와 질문을 고정하고 E5 Dense/Hybrid를 비교합니다. 검색법만 바꿔 차이를 봅니다.
3. 같은 검색법에서 E5/BGE를 바꿉니다. 모델 identity가 바뀌면 새 문서 벡터가 필요합니다.
4. candidate-k는 각 검색기의 결합 전 후보 수, top-k는 결합 후 최종 후보 수입니다. RRF 상수는 순위 기여의 차이를 조절합니다. 그 뒤 whole-chunk 문자 예산을 적용합니다.
5. 후보의 BM25/Dense rank·원점수·기여를 보고, 실제 포함·예산 제외와 원문 위치를 대조합니다. 좋은 후보가 있어도 예산으로 빠질 수 있습니다.

수기 예: BM25=`a,b,c`, Dense=`b,d,a`, 상수60이면 `b=1/62+1/61`, `a=1/61+1/63`, `d=1/62`, `c=1/63`으로 `b,a,d,c`입니다. 한 검색기가 실패하면 전체 Hybrid 실패이며 BM25로 자동 대체하지 않습니다. 정상적인 빈 BM25 목록은 Dense 기여만으로 결합할 수 있습니다. Dense의 0·음수 점수도 후보로 남깁니다.

## 검색 평가와 답변 평가

CLI compare의 `--qrels 파일.json`은 같은 source/chunk/questions fingerprint에 묶인 **청크 검색 정답**입니다. schema1은 source_fingerprint, chunk_fingerprint, questions_hash, judgments_complete, judgments(질문 ID→청크 ID→0/1/2 등급)를 요구합니다. 중복키·알 수 없는 ID·다른 corpus는 오류입니다. 청킹을 바꾸면 기존 청크 qrels를 재사용할 수 없습니다.

명시적으로 judgments_complete=true일 때만 미기재 청크를 0으로 봅니다. 불완전하면 N/A입니다. Precision@K는 관련 회수/K, Recall은 관련 회수/전체 관련, MRR은 첫 관련 순위의 역수, nDCG는 등급별 gain으로 이상 순위와 비교합니다. 관련 청크가 없는 질문은 Precision=0, Recall/MRR/nDCG=null이며 no_answer 그룹으로 구분합니다. macro에는 valid/제외 수와 이유 및 별도 그룹을 남기고 실패를 성공 0점으로 계산하지 않습니다.

지표는 개별 answer artifact를 봉인하기 전에 계산하여 compare 행과 상세 result.json에 동일하게 저장합니다. 답변의 Faithfulness/Correctness는 여전히 N/A입니다. 개발 fixture의 수기 qrels는 승인 HR GT·독립 holdout이 아닙니다. 현재 화면에는 qrels 업로드가 없으며 CLI에서 지정합니다.

실습 기록에는 예상 순위, 실제 순위, 누락된 근거, 바꾼 변수, latency, 문서/query 작업 수를 남기세요. RSS는 worker의 OS peak 관측이며 모델 상주 메모리만을 뜻하지 않습니다. 비용은 미측정입니다. 후속 S1의 고정 규정집 결과와 관측 메모리는 [실제 비교 안내](live-retrieval-s1.md)에 있으며 일반 한국어 품질을 보장하지 않습니다. 다음 실습은 [고정 후보 리랭커](reranking.md)이며 평가기 실험 보류는 유지됩니다.

검증한 패키지 소스: `8e7ef784377043c9b8653ef87a254015c4eb90eb` (personal/dev). 설치 안내의 P028 고정 checkout 대신 이 SHA를 사용해 빌드합니다. 같은 0.1.0.dev1 이름이라도 wheel hash로 배포물을 구분하세요. [최종 배포물 hash](../../verification/p010/installation.json)와 [전달 기록](../../verification/p010/delivery.json)을 함께 확인합니다.
