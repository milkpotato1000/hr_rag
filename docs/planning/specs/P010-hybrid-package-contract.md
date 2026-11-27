# P010 — 공개 임베딩·Dense/BM25/Hybrid 구현 계약 v1

2026-11-28. 사용자가 평가기 실험을 보류하고 Hybrid→리랭커 구현을 먼저 진행하도록 명시했다. P013/P014 실험 및 P008 평가 UI는 선행에서 제외한다. P013 보류·GT·grant·기존 실패는 유지한다. **이번 카드는 실제 사용 가능한 검색 코드와 오프라인 검증**이다. 사전학습 가중치 실행·한국어 품질 실험은 완료 조건으로 위장하지 않고 후속 live 검증 대상으로 남긴다.

## 기반·파일·실행 범위

- 기반은 dev/personal-dev `78b85c8dbd4c34ec06a429384a3910d5fbd8625e`: P026 일반 문서 코어, P028 설치 패키지, P029 전달된 C1~C3 UI. P029 C4 파일 선택창 검증은 미완료이며 이 카드가 그 체크를 승계하거나 정책 우회를 시도하지 않는다. 이 미완료 항목은 신규 검색 구현의 선행이 아니다.
- `rag_package/` 검색·설정·선택 HF adapter/격리 worker·CLI·UI, `tests/rag_package/`, packaging allowlist/optional extras, 가이드·검증이 범위다. 기존 BM25 schema v1 입력과 저장 artifact를 계속 읽고, 새 schema는 version으로 구분한다. 무조건 기존 artifact를 마이그레이션/덮어쓰기하지 않는다.
- `3. Hybrid RAG/`는 새 큰 학습 단계다. 공통 패키지의 설치/실행 설정·합성 실습 자료·README·stage-manifest.json을 두고 패키지를 재사용한다. 이전 단계 전체를 복제하거나 숨은 상대경로로 의존하지 않는다. 필요한 이전 코드/자료만 commit/path/SHA256과 함께 선별한다. 다른 폴더에서도 설치 패키지로 실행되는 stage 실습을 검증한다.
- P011 ADOPT_LANGCHAIN 판정과 P012 기존 UI는 보존한다. 고정 HR LangChain 구현을 직접 구현으로 되돌리지 않는다. 새 범용 package에는 이미 전달된 provider/문서 코어를 확장하며 프레임워크 재비교는 하지 않는다.
- dev는 실제 optional SDK와 호출 코드를 구현한다. fake vector를 production 기본값으로 사용하지 않는다. 미설치·미설정·실행 미허용은 명확한 오류다. 실제 모델 가중치 다운로드/로드, Ollama 시작, 유료 API/Drive/OAuth/키, 평가기 실행은 이번 검증에서 하지 않는다.

## HF 임베딩 경계

초기 선택은 `intfloat/multilingual-e5-small`(MIT,384차원,query/passage 접두어,최대512토큰)과 `BAAI/bge-m3`(MIT,1024차원,접두어 없음,카드 최대8192토큰)의 Dense 출력이다. BGE의 learned Sparse/Multi-vector 출력은 이번 범위가 아니며 Sparse 선택은 기존 BM25다. 모델별 전처리는 고정 catalog entry로 관리한다. 모델명을 바꿔 놓고 이전 전처리·차원·출처를 재사용하지 않는다. 라이선스/공식 링크/한국어 미검증 표시를 제공한다.

선택 HF profile JSON은 strict schema/version과 `model_id`,40hex `revision`,`local_path`,`file_manifest`(실제 설정·tokenizer·가중치 파일 SHA256),`device`(cpu/mps),`dtype`(float32),`max_input_tokens`,`batch_size`(1..8),`timeout_seconds`(1..300),`max_chunks`(1..5000)을 가진다. 기본 cpu/batch1/max_input_tokens512(모델 고유 한도와 구분)/timeout120/max_chunks2000. 두 모델의 실제 revision/파일 manifest가 없는 예시는 placeholder이며 실행 금지다. HF 원본 ID와 GGUF/Ollama digest를 동일하게 취급하지 않는다. registry 경로는 CLI에서만 등록하고 웹에서 arbitrary 경로·코드를 받지 않는다.

실제 adapter는 SentenceTransformer의 torch backend를 사용하되 로컬 snapshot만, `local_files_only=True`, `trust_remote_code=False`, `token=False`, offline 환경으로 실행한다. 사전 실행 파일 hash·모델/차원·전처리 일치를 검증한다. 원격 custom code·pickle 가중치를 로드하지 않고 safetensors를 사용한다. Hugging Face cache의 symlink를 임의 해제해 허용하지 않는다. 사용자가 export한 자체 완결된 nonsymlink 디렉터리를 안내한다. 파일 manifest는 root 아래 regular file만, 상대경로 탈출/중복 거부. config/tokenizer 포함 최대100파일/전체4GiB 상한; 메타데이터 hash 검사도 경로 밖 파일을 읽지 않는다.

P026 청크 text를 그대로 임베딩하며 질문/문서 prefix 적용 뒤 special tokens를 포함한 tokenizer 길이를 확인한다. 초과하면 offending chunk IDs 또는 query와 `input_too_long`을 반환하고 silent truncation/자동 재청킹하지 않는다. E5의 normalized average pooling, BGE의 모델 정의 pooling을 선택 revision의 실제 SDK 동작으로 확인한다. 반환 vector의 개수·차원·finite·nonzero를 검증하고 L2 normalize한다. 단순 hashing embedding을 실제 모델로 표시하지 않는다.

HF runtime은 요청별 격리 subprocess, 단일 worker로 순차 로드/종료한다. 한 job에 사전학습 모델을 여러 개 상주시켜 비교하지 않는다. timeout 시 소유 worker만 종료하고 프로세스 종료를 확인한다. 기존 사용자 모델 서버는 종료하지 않는다. RSS는 관측 peak/샘플 주기와 한계를 기록하고 unavailable이면 null; 모델 크기로 메모리 사용을 추정해 실측으로 표기하지 않는다. index 파일은 vector numeric array만 저장하고 실행 코드/pickle을 읽지 않는다.

core 설치는 표준 라이브러리를 유지한다. optional `[retrieval]`에 Sentence Transformers/torch/transformers를 추가한다. dev가 공식 PyPI의 Python3.12/macOS-arm64 호환 버전을 resolve하고 **설치 전에** 정확 버전·hash lock과 출처를 증거로 기록한다. 현재 사용자 환경을 업그레이드하지 않고 격리 venv 사용, sdk 의존성 설치만 허용(모델 가중치0). 기존 잠금 버전을 조용히 바꾸지 않는다. 패키지 기본 Python3.10 지원과 retrieval extra의 실제 검증 버전/지원 플랫폼을 구분한다. tiny locally-generated random model로 실제 SDK serialization/tokenization/encode를 검증할 수 있다(최대10M parameters/512MiB artifact, 품질 증거 아님). 가용 환경에서 SDK 설치가 막히면 C1/C4 미완료로 남기고 fake-only로 완료하지 않는다.

## 설정·색인·순위

신규 RAG schema v2: 기존 chunking/llm_config를 유지하고 `retrieval={method,top_k,context_budget_chars,candidate_k,rrf_k}` 및 `embedding_config`(설정 파일 경로; BM25는 null)를 추가한다. method는 bm25/dense/hybrid. top_k1..100, candidate_k1..1000, candidate_k>=top_k, rrf_k1..1000(기본60). BM25에서도 무의미한 embedding 설정을 자동 실행하지 않는다. 파라미터 추가 필드와 잘못된 조합은 거부한다. max_chunks/차원/예산을 사전 확인하고 대규모 자동 sweep은 없다.

색인은 source/chunk identity에 HF ID/revision/파일 hashes/SDK 버전/전처리·정규화·dimension·dtype/device와 알고리즘 버전을 포함한다. source/청킹/embedding 변경은 새 색인; top_k/candidate_k/rrf_k/문맥예산/LLM만 바꾸면 vector를 재생성하지 않는다. BM25와 Dense가 **동일 chunk ID 집합과 text hash**를 사용한다. artifacts는 immutable/no-clobber, load 시 hash/identity 검사, stale이면 명시 재구축 경로 안내. 모델을 재로드해 문서 vector를 비교 재계산하지 않고 저장 artifact를 검증한다.

Dense는 작은 학습 corpus의 정확 cosine 검색으로 시작한다(ANN 근사 오차와 분리). normalized dot score 내림차순, 동일 score는 chunk ID 오름차순. 음수/0도 임의로 버리지 않고 top 후보를 보존한다. BM25는 기존 양수 score만/동점ID 정렬을 유지한다. 두 목록 각 candidate_k에서 RRF `sum(1/(rrf_k+rank))`, rank는1부터, 누락 목록 기여0, chunk ID로 중복 제거한다. 동일 RRF score는 chunk ID 오름차순. raw BM25와 cosine를 직접 더하지 않는다. 계산은 원 정밀도로 하고 표시에만 반올림한다. 구성 검색기가 실패하면 전체 hybrid 실패, BM25 자동 fallback 금지. 정상적인 빈 BM25 결과는 실패가 아니며 Dense 목록의 기여만으로 결합할 수 있다.

RRF 수기 기대값: BM25=[a,b,c],Dense=[b,d,a],rrf_k=60이면 b=1/62+1/61, a=1/61+1/63, d=1/62, c=1/63, 순위 b,a,d,c. 중복 입력 ID는 잘못된 검색 결과로 거부한다. 최종 top_k 뒤 기존 whole-chunk 문자예산 선택을 적용한다. 원본 후보 목록·각 rank/score·RRF 기여·최종 순위·실제 전달/제외를 결과에 보존한다. ID-only 인용과 코드 원문/페이지 연결은 유지한다.

## CLI·UI·실행 의미

`rag-lab build/ask/compare` 기존 사용법은 BM25에서 그대로 동작한다. Dense/Hybrid의 HF 계산에는 별도 `--execute-retrieval`을 요구한다. 기존 `--execute`는 생성 LLM만 의미한다. retrieval 허용만으로 LLM/평가기 호출하지 않는다. 필요한 vector가 없고 flag도 없으면 `retrieval_execution_required`와 예상 작업을 반환하며 BM25/fake로 대체하지 않는다. 계산 없이 설정만 검사할 별도 preview/dry-run을 제공한다. CLI 실행 결과는 embedding 작업 수·문서/query 수·생성 요청 수를 구별한다. 캐시된 문서 vector로 search할 때 query embedding도 계산이 필요함을 설명한다.

UI startup에 `--embedding-config` 등록(최대4)과 `--allow-retrieval-execution` 기본false를 추가한다. 웹에는 opaque ID만 전달하고 source path/key/모델 파일 경로를 편집시키지 않는다. HF ID/license/설정 여부/한국어 미검증과 로컬 계산 필요를 표시한다. 선택한 검색법과 HF profile·candidate_k/RRF상수/top_k/문맥예산을 구분하며 settings clone/compare는 동일 source/questions에서 가능하다. 기본 BM25는 유지하되 Dense/Hybrid를 선택하면 flag/config 미충족 이유를 보여준다. 서버 등록 모델이 없을 때 fake 모델이나 빈 점수를 정상 기능처럼 보여주지 않는다.

UI 단일 job/중복ID/재시작 interrupted와 secret/no-network 기본 경계를 계승한다. 비교는2..4설정×1..20질문, 임베딩 모델 순차 worker, 실패행 포함. generation preview와 retrieval 실행 여부를 별도로 표시한다. 실제 API 선택은 LLM에만 적용된다. 지원 옵션·설정 바뀐 축과 원문/청크/후보/전달/인용을 연결한다. P029 filechooser 제한은 우회하지 않으며 등록된 합성 파일로 신규 검색 UI를 관찰한다.

## 검색 평가와 검증

답변 평가기 없이도 qrels를 사용한 검색 평가는 가능하다. optional 별도 qrels schema는 source_fingerprint/chunk_fingerprint/questions_hash와 질문별 `{chunk_id:grade}`(0,1,2)를 고정한다. unknown IDs/다른 corpus·질문 fingerprint/중복은 오류. 명시적 `judgments_complete=true`인 학습 fixture만 미기재 청크를0으로 간주한다. 완전성 미확정 qrels는 품질 N/A이며 임의 0라벨로 보완하지 않는다. 관련=grade>0. Precision@K=관련 회수/K(후보 부족분0),Recall@K=관련 회수/전체관련,MRR@K=첫관련rank 역수,DCG=sum((2^grade-1)/log2(rank+1)),nDCG=DCG/전체 corpus qrels의 상위K IDCG. 관련0이면 Recall/MRR/nDCG는 null(reason=no_relevant), Precision은 검색 결과 의미와 함께 별도 no-answer 그룹으로 표시한다. macro 평균은 valid수/제외수·이유를 병기하고 실패행을 성공0점으로 섞지 않는다. 생성 Faithfulness/Correctness는 계속 N/A다.

새 합성 소규모 qrels는 수기 기대값용 개발 fixture로 표시하고 HR 승인 GT/독립 holdout이라고 부르지 않는다. 기존 P007 사실/span 비교는 별도 보존하고 청크 qrels와 Reference Claims를 혼용하지 않는다. 한국어 실모델 검색 비교·실제 생성 품질·자원 실험은 후속 live 카드에서 수행해야 전체 goal을 완료할 수 있다.

필수 시험: 알려진 orthogonal/음수/동점 vector와 hand-computed RRF, prefix/길이초과/zero·NaN·차원/count 오류, index identity 재사용/변조, qrels 독립 기대값·관련없음·중복·실패분모, 두 모델선택·BM250embedding·명시 flag, timeout/단일worker/재시작/파일 실패, fake 답변 citation whitelist, 기존 v1 전체 회귀. fake 주입은 test_fixture로 UI/산출물에 자동 표시하며 production 옵션으로 노출하지 않는다. 공식 SDK tiny local model 시험은 별도 라벨로 기록한다.

새 wheel/source 없는 cwd에서 stage 실습·CLI와 UI asset 동작, 실제 허용 browser로 검색법·모델 변경/후보기여/예산제외·비교/좁은 화면/키보드 확인. 브라우저 거부는 우회하지 않고 해당 기준 미완료로 남긴다. P025~P029 회귀, 과거 단계·GT·P013/grant hash 보존, 소유 검증 프로세스 종료. 결과 docs/verification/p010/, 가이드 docs/learning/rag-package/hybrid.md. actual pretrained embedding/LLM/API/Drive0과 미검증 live 항목을 명확히 보고한다.

## 조사 근거

[HF 후보 조사](../reviews/hf-model-candidates-20261127.md), [SentenceTransformer 공식 API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html), [E5 카드](https://huggingface.co/intfloat/multilingual-e5-small), [BGE-M3 카드](https://huggingface.co/BAAI/bge-m3). 공식 문서는 revision/local_files_only/token/trust_remote_code 설정을 제공한다. 이 계약의 실행 flag·길이 거부·수기 기대값은 프로젝트 정책이며 모델 제작사의 성능 보증이 아니다.
