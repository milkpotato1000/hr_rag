# P020 리랭커 설계 초안 — 2026-11-28

**DRAFT / 실행 계약 아님.** P010 구현 중 준비하는 후속 설계다. 사용자 결정에 따라 P010→P020이며 평가기 실험은 보류한다. P010의 커밋된 후보 artifact·SDK worker·설정/CLI/UI 형식을 대조한 후 READY로 확정한다. 이 파일만으로 dev 구현/모델 실행을 시작하지 않는다.

## 학습자가 비교할 것

동일한 원문·청킹·질문·검색 설정에서 한 번 확보한 후보 N개를 고정한다. `none`(검색 원래 순위)과 선택한 HF reranker를 비교한다. 원문/임베딩/Hybrid를 동시에 바꾸지 않는다. 후보에 없는 정답은 리랭커가 복원할 수 없으므로 먼저 후보 N개의 관련 근거 회수율을 보여준다. 최종 K개에서의 순위 효과와 문자 예산 적용 후 실제 전달 근거를 별도 표시한다.

학습 화면의 핵심 흐름은 후보 snapshot 선택 → reranker off/on·모델 선택 → 전후 순위/원문 → 검색 지표/추가 지연 → 필요한 경우 최종 답변 입력에 연결이다. 답변을 생성하거나 평가하지 않고도 검색 단계의 비교를 완료할 수 있어야 한다.

## 공개 모델 후보 조사

모두 2026-11-28 공식 카드 관찰이며 실제 모델을 실행하지 않았다. 다운로드/likes는 시점별 참고값으로 한국어 품질·속도·메모리를 보장하지 않는다.

| 후보 | 공개 근거 | P020에서의 역할 |
| --- | --- | --- |
| BAAI/bge-reranker-v2-m3 | [카드](https://huggingface.co/BAAI/bge-reranker-v2-m3), Apache-2.0, 다국어 Cross-Encoder | 초기 기본 후보. query/document 쌍의 단일 logit으로 순위화 |
| cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 | [카드](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1), Apache-2.0, 페이지 약0.1B, 월 다운로드1,113,277/likes100 | 더 작은 다국어 비교 후보. mMARCO 번역 학습 설명을 한국어 HR 검증으로 오해하지 않음 |
| Qwen/Qwen3-Reranker-0.6B | [카드](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B), Apache-2.0, instruction 기반 | 다른 채점 구조를 학습할 추가 후보. READY 전 SDK/template 경계 검토 필요; 검토만으로 지원 기능에 넣지 않음 |

[BGE config](https://huggingface.co/BAAI/bge-reranker-v2-m3/raw/main/config.json)와 [MiniLM config](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/raw/main/config.json)는 모두 XLMRobertaForSequenceClassification, 단일 label을 명시한다. position embedding 숫자8194/514를 곧바로 사용자 입력 한도로 표시하지 않고, 실제 tokenizer의 pair special tokens를 포함한 길이를 검증한다. MiniLM config는 Identity activation을 명시한다. 실제 사용할 revision의 config/tokenizer/가중치 hash와 라이선스를 고정해야 한다.

Qwen 공식 예시는 next-token yes/no logit 차이를 점수화하며 instruction/chat template이 포함된다. 문장을 생성시켜 자유로운 숫자를 파싱하는 방식과 다르다. 위 두 sequence classifier와 동일한 전처리로 교체하면 안 된다. SDK가 해당 경로를 지원하는지 실제 선택 버전으로 확인한 뒤 별도 adapter를 확정하거나 명확히 후속으로 남긴다.

## 후보 artifact와 순위 계약 초안

- P010의 검증된 build, query hash, source/chunk/index fingerprints, 검색 설정/실행 kind, branch ranking·RRF 결과에서 **N개 전체 후보**를 고정한다. 최종 top_k/문맥 예산으로 이미 줄어든 contexts만 rerank 입력으로 쓰지 않는다.
- N은1..100, 기본20, K는1..N 기본5. 실제 corpus/검색 후보가 N보다 적으면 실제 개수와 부족분을 기록한다. 전체 corpus qrels의 관련 수를 작은 후보 집합의 관련 수로 바꾸지 않는다.
- candidate snapshot에는 순서·ID·정확 canonical text hash·원문 metadata를 묶는다. off/on/모델별 비교 중 재검색/재임베딩/원문 재파싱을 하지 않는다. 다른 source/query/후보 hash를 같은 paired 비교로 묶지 않는다.
- 모든 후보에 score를 받고 개수/순서 mapping/ID 유일성/finite를 검증한다. 누락된 score, NaN, unknown ID가 있으면 그 질문의 재정렬 실패다. 일부 성공 후보만으로 정상 순위 만들지 않는다.
- 정렬은 raw score 내림차순, 동점은 기존 검색 rank, 이후 chunk ID 순. score를 표시용으로 반올림한 뒤 정렬하지 않는다. 서로 다른 모델의 raw score를 합치거나 같은 관련성 확률로 비교하지 않는다. none은 원 순위를 그대로 보존한다.
- top K를 고른 뒤 기존 whole-chunk 문자 예산을 적용한다. 전체 N개를 점수화한 비용과 최종 전달 K/예산 효과를 구분한다. 모델별 낮은 점수를 근거로 자동 답변 보류 임계값을 발명하지 않는다.
- 새 artifact는 immutable, provenance/hash 검증, no-clobber. 저장된 rank/score/qrels로 보고서를 재생할 때 모델/키/네트워크를 호출하지 않는다. 원래 후보 artifact를 overwrite하지 않는다.

## 실행·자원·오류 경계 초안

P010의 SDK lock/격리 worker를 재사용하고 실제 CrossEncoder 호출 경로를 구현한다. local_files_only/trust_remote_code=false/token=false/safetensors·파일 hash 검사, CPU float32 기본, 단일 worker 순차 실행을 유지한다. P020에서 다른 의존성 버전이 필요하면 원인·호환성을 먼저 기록하고 기존 P010 회귀를 통과시킨다.

기본 max_pair_tokens512(사용자 설정값, 모델 고유 한도와 구분), batch1, timeout120초. query와 passage를 pair tokenizer에 넣은 전체 길이를 측정한다. 초과하면 해당 질문의 rerank를 명시 실패시키며 조용한 truncate/일부 청크 제거/LLM 요약을 하지 않는다. 원문 청크를 수정하지 않고 이후 별도 실험에서 청킹·길이 정책을 바꾸게 안내한다.

UI/CLI에 reranking 계산 실행 허용을 생성 및 임베딩 계산과 구분한다. 허용 flag·실제 profile이 없으면 설정 preview만, fake/default score0으로 순위를 만들지 않는다. none은 reranker worker를 호출하지 않는다. fixed candidate 비교에서는 embedding도 호출하지 않아야 한다. 실제 model/API/Drive/평가기/키 호출은 개발 fixture 검증에 포함하지 않는다.

검증용 모델은 tiny local random sequence classifier(최대10M parameters)로 SDK 토큰화/score shape/serialization/프로세스 종료를 확인한다. 주입 점수의 수기 fixture와 실제 SDK 시험을 별도로 표시한다. 한국어 retrieval 성능 근거로 쓰지 않는다. 사전학습 모델 live 비교/메모리 실험은 별도 실행 계약이 필요하고 P013 보류는 유지한다.

질문1..20, none 포함 설정2..4, N≤100이면 비교 점수화 상한은 최대6,000 pair(3개 모델×20질문×100)다. 구현 검증은 이 최대치 전수 실행을 요구하지 않는다. retry0, timeout/저장 실패 후 자동 재호출0. pair 수·query 수·worker 수·load/score/전체 지연을 구분하며 peak RSS 관측 한계를 명시한다. generation 비용과 혼동하지 않는다.

## 지표와 독립 기대값

기본 청크 qrels와 P/R/MRR/nDCG 산식은 P010을 계승한다. 후보 N의 recall과 최종 K의 recall을 별도로 표시한다. 주 지표 nDCG@K/MRR@K와 Precision/Recall, 질문별 변화, 유효/실패/제외 분모를 기록한다. 관련 근거가 없는 질문의 nDCG/MRR/Recall은 N/A 그룹이며 임의0점으로 평균하지 않는다. qrels 완전성 미확정·fingerprint 불일치는 명확한 상태다. 자동 답변 Faithfulness/Correctness는 여전히 N/A다.

수기 fixture: 전체 corpus qrels `a:2,b:1,c:0,d:2`; 후보[a,c,b],K=2. none[a,c]는 Precision=.5, Recall=1/3, MRR=1, DCG=3, IDCG=3+3/log2(3). rerank[a,b,c]는 Precision=1, Recall=2/3, MRR=1, DCG=3+1/log2(3), IDCG는 동일하다. 누락된 d가 IDCG/Recall 분모에서 사라지면 안 된다. 후보 전체 recall은 양쪽 모두2/3이며 리랭커가 이를 개선했다고 보고하면 오류다. MRR은 같지만 nDCG/Recall이 달라지는 이유를 설명한다.

필수 fact/span 정답이 별도로 제공되면 source fingerprint와 정확 document/page/canonical intervals를 연결한다. 하나의 fact가 여러 필수 span을 요구할 때 선택 청크들의 interval union이 전부 커버해야 해당 fact1건으로 센다. 중복/overlap 청크가 같은 fact를 여러 번 가산하지 않는다. `fact_recall=충족 필수 fact/전체 필수 fact`, `all_required=모든 필수 fact 충족 여부`. 여러 대체 근거 중 하나만으로 충분한 경우는 alternatives로 명시하며 AND/OR를 추측하지 않는다. fact/span 입력이 없으면 해당 지표만 N/A로 남긴다.

## P010 구현을 보고 확정할 항목

1. 완료 commit·실제 schema/worker public entrypoint·candidate/full-ranking 저장 위치와 hash.
2. SDK pin·CrossEncoder 지원과 모델별 activation/template/길이 검증, 실제 초기 지원 모델 목록.
3. rerank/replay CLI와 ask/compare 통합 방식, 전송 허용 flag, UI registry·job payload/version.
4. optional fact/span 입력 schema, 개발 fixture·qrels hash·수기 기대값·테스트 경계.
5. wheel/3.Hybrid 실습/허용 browser 검증과 C1~C4, actual pretrained model0·live 미검증 보고.

P029의 파일 선택창 접근 거부를 재시도 우회하거나 검증된 것으로 처리하지 않는다. 신규 rerank UI는 등록된 합성 candidate artifact로 관찰한다. P010 구현이 완료되지 않았는데 본 초안을 근거로 P020를 자동 시작하지 않는다.

## P010 연결 상세 초안 — 2026-11-28 코드 관찰

다음은 P010 dev HEAD `e354abd` 위의 작업 중 코드 관찰에 따른 설계이며 완료 인터페이스의 보증이 아니다. READY 검토에서 커밋된 최종 코드와 다시 대조한다.

현재 `retrieval.select`는 `rows`를 top_k까지 줄여 반환하지만 `retrieval_trace.bm25`와 `.dense`에 branch 후보를 보존한다. P020 후보 생성은 이 branch 목록과 저장된 검색 설정을 사용하여 전체 결합 순위를 재구성한다. Hybrid는 기존 `rrf` 함수를, Dense/BM25는 해당 branch 순위를 사용한다. 재구성한 top_k가 원 결과의 candidates와 일치하는지 검사한 뒤 앞 N개를 고정한다. branch의 candidate_k가 요청 N보다 작다면 `candidate_depth_insufficient`로 명시하고 충분한 candidate_k의 검색을 따로 수행하도록 안내한다. corpus가 작거나 BM25 양수 결과가 적은 정상적인 후보 부족과 설정 깊이 부족을 구분한다. 과거 artifact에 branch trace가 없으면 contexts를 후보인 것처럼 대체하지 않는다.

후보 고정은 이미 저장된 answer/검색 결과 artifact와 대응 build를 검증한 뒤 실행한다. 원문·청크·index fingerprint, query hash, effective retrieval settings, branch 순위·점수와 실제 chunk ID/text hash를 일치시킨다. 원래 답변이 생성 실패했더라도 검색 단계와 후보가 온전하면 검색 후보는 사용할 수 있다. 검색 단계 실패나 잘못된 artifact는 불가하다. 기존 answer JSON을 고쳐 rerank 결과를 끼워 넣지 않는다.

새 candidate artifact v1의 필수 내용:

- `source_fingerprint`, `chunk_fingerprint`, `index_fingerprint`, `query_hash`, `question_id`, `question`, `retrieval_settings`, `origin_result_fingerprint`, `execution_kind`.
- `requested_n`, `actual_n`, `candidate_depth`, `shortage_reason`, 원 순서의 `candidates`. 각 행은 `chunk_id`, `original_rank`, `retrieval_score`, `text`, `text_hash`, `document_id`, `start`, `end`, `pages`, `heading_path`를 가진다. page는 원문 매핑에서 유도하며 임의 입력으로 신뢰하지 않는다.
- source canonical text/page mapping 및 후보를 검증할 최소 원문 snapshot을 함께 보존한다. 모든 corpus의 chunk ID·구간 목록도 보존하여 qrels의 unknown ID를 검증한다. vector와 embedding profile 경로는 후보 재생에 필요하지 않다.
- `candidate_fingerprint`는 질문·출처·검색 identity·순서·본문 hash를 포함한다. 같은 text라도 source/revision/query가 다르면 같은 비교쌍으로 취급하지 않는다. 실제 비교에서는 입력 값의 fingerprint를 재계산하고 저장된 문자열만 믿지 않는다.

후보 manifest에는 qrels/GT를 넣지 않는다. qrels와 fact/span 정답은 평가 입력으로 별도 고정하고 result에는 그 hash만 provenance로 연결한다. worker payload는 질문, 후보 ID/본문, 모델 profile만 받는다. grade, fact 정답, 기대 순위, 기존 답변, 모델별 점수, 비교군 이름은 모델 입력에 포함하지 않는다. UI의 주입 fixture는 production 선택 목록에 넣지 않는다.

### 사용자 실행 동선 초안

1. `rag-lab candidates --build ... --result ... --n 20 --out ...`: 저장 결과에서 후보 고정. 모델/embedding/LLM 호출0.
2. `rag-lab rerank --candidates ... --profile ... --top-k 5 --context-budget-chars ... --out ...`: 기본 preview; `--execute-reranking`이 있어야 실제 score 계산. `--method none`은 profile 없이 원 순위를 재사용한다.
3. `rag-lab rerank-compare --candidates-set ... --variants ... --qrels ... --facts ... --out ...`: 같은 질문별 후보에 none과 모델을 순차 비교. qrels/facts는 선택 입력. 실행 허용은 생성·embedding flag와 독립이다.
4. `rag-lab rerank-report --run ...`: 검증된 결과의 재생. 저장된 score와 순위로 표를 재구성하고 모델/SDK import/키/네트워크0. 재생과 재채점을 혼동하지 않도록 표시한다.
5. 선택한 rerank 결과의 contexts를 기존 generation provider에 연결할 별도 경로를 제공한다. 이 경로는 결과/후보를 검증한 뒤 K와 문자 예산의 선택을 재현하고, 기존 ID-only citation 검증을 재사용한다. 재검색·재임베딩·재리랭킹 없이 generation만 실행할 수 있어야 한다. 기본은 generation preview이며 별도 `--execute`만 LLM 호출을 허용한다. 기존 ask 설정에 reranker 이름만 추가하고 실제로 무시하는 구현은 허용하지 않는다.

CLI 명령명은 최종 READY에서 고정한다. UI도 같은 코어를 호출하고 candidate/result opaque ID를 선택하며 서버에 등록한 reranker profile만 사용한다. URL/path·동적 Python·model ID 자유입력을 브라우저에서 실행하지 않는다. 기존 단일 job/idempotency/restart 정책을 계승한다. qrels/facts 등록도 서버 측 읽기 경로에서 검증하고 웹에는 ID만 노출한다. qrels가 없어도 순위/원문/비용 비교는 가능하고 품질 지표만 N/A다.

## Fact/span 입력과 검증 예시 초안

optional facts v1은 `schema_version`, `source_fingerprint`, `questions_hash`, `offset_unit="unicode_codepoint"`, `questions`를 가진다. 질문별 항목은 `question_id`, `required_facts`이며 각 fact는 고유 `fact_id`와 비어 있지 않은 `alternatives`다. 하나의 alternative는 **모두 필요한** `spans` 배열이며 각 span은 `document_id`, `start`, `end`, `quote`다. alternatives 중 하나의 모든 spans가 커버되면 그 fact를1회 센다. 의미 추론이나 임의 조항 확장을 하지 않는다.

source의 NFC/LF canonical text에서 `[start,end)`가 정확 quote와 일치해야 한다. byte/UTF-16/PDF 화면 좌표가 아니다. page는 canonical page mapping으로 유도한다. 범위 밖/빈 구간/없는 문서/중복 fact ID/중복 JSON key/잘못된 타입·추가 필드는 거부한다. 다른 source나 question set 정답을 조용히 재사용하지 않는다. fact 위치는 chunking과 독립이지만 선택 chunk의 source identity는 동일해야 한다. 질문당 최대100 facts, fact당 최대4 alternatives, alternative당 최대8 spans로 입력 규모를 제한한다. facts가 없으면 N/A이며 empty required_facts는 `no_required_facts`로 분모0을 별도 표시한다.

각 단계별 선택 청크의 구간을 document별로 합집합한다. 겹치거나 맞닿은 구간은 병합하되 서로 다른 문서의 동일 숫자 구간을 합치지 않는다. 다음 세 집계를 각각 남긴다: 후보 N 전체, 최종 K(문자 예산 전), 실제 contexts(문자 예산 후). 필요 fact 수와 충족 fact ID·대안·span별 커버 여부를 기록해 수치를 원문으로 추적한다.

독립 기대값은 다음과 같다. 동일 문서 d에서 f1은 `[0,5)` AND `[10,15)`, f2는 `[20,25)` OR 대체 문서 e의 `[0,5)`를 필요로 한다. 선택 청크가 d:`[0,3)`, d:`[3,5)`, d:`[10,15)`이면 f1만 충족하여 fact_recall=1/2, all_required=false다. d:`[0,3)`을 중복해도 점수는 같다. 여기에 e:`[0,5)`를 추가하면2/2,true다. d:`[3,5)`가 예산에서 제외되면 f1이 다시 미충족이며 f2만 남아1/2,false다. d:`[0,3)`과 e:`[3,5)`를 합쳐 d의 `[0,5)`를 충족했다고 판단하면 오류다. 이 시험은 span 회수율 검증이며 생성 claim의 Faithfulness/Correctness 시험이 아니다.

## READY 전 남은 확인

P010 tiny SDK 증거는 Sentence Transformers6.3.0/torch2.15.0/transformers5.24.1/tokenizers0.23.3/safetensors0.8.0의 실제 임베딩 호출을 보였지만 CrossEncoder 지원 증거는 아니다. P020는 이 잠금을 그대로 쓸 수 있는지 해당 설치 코드/API를 읽고 tiny sequence classifier로 별도 확인하도록 계약한다. 라이브 가중치 실행을 tiny 성공으로 갈음하지 않는다. P010 전체 회귀·설치·화면·완료 SHA가 확보된 뒤 위 입력/출력·CLI·모델 목록·기대값을 최종 계약으로 검토한다.
