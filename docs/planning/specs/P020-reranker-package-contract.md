# P020 — 고정 후보 리랭킹·비교·답변 연결 계약

2026-11-28. **준비 검토 전 초안**. P010 최종 완료 SHA를 확인하고 P020 카드/readiness를 함께 확정해야 실행 계약이 된다. 이전 [설계 조사](P020-reranker-design.md)는 근거이며 최종 READY 이후 충돌 시 본 계약을 우선한다. 사용자 순서는 Hybrid→리랭커, P013/P014 평가기 실험은 보류 유지다.

## 범위와 보존

P010 공통 `rag_package/`, CLI/UI/설치 패키지와 `3. Hybrid RAG/`를 확장한다. `none`과 공개 HF Cross-Encoder 두 모델을 선택·동일 후보에서 비교하고, 선택한 결과의 문맥을 기존 generation provider로 연결한다. 검색 순위 평가와 답변 평가를 구분한다. 기존 schema v1/v2·CLI·artifact와 P001~P029 단계/GT/실패/보류를 보존한다. P029 C4 파일 업로드 화면 차단을 우회하거나 완료로 승계하지 않는다.

이번 검증은 사전학습 가중치 다운로드/로드0, LLM/API/Drive/OAuth/개인키 호출0이다. 실제 SDK adapter와 tiny 무작위 sequence classifier, 독립 수기 score fixture를 모두 사용한다. 실제 한국어 품질·사전학습 메모리·최종 답변 품질은 후속 live 검증으로 남는다. fake-only production이나 이름만 다른 동일 scorer를 여러 모델 지원으로 표시하지 않는다.

## 모델과 실행 profile

초기 지원은 `BAAI/bge-reranker-v2-m3`와 `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`. 공식 카드 Apache-2.0·다국어 범위/한국어 미검증을 카탈로그에 표시한다. 두 모델은 XLMRobertaForSequenceClassification의 단일 logit을 사용한다. 후보 조사/공식 링크는 설계 문서를 따른다. Qwen3 instruction reranker는 이 계약에서 미지원 후보로 명시한다. 별도 template/token 검증 없이 자동 활성화하지 않는다. 유료 API는 기존 LLM 역할에만 선택할 수 있다.

strict profile v1 필드: `schema_version`, `model_id`, `revision`(40hex), `local_path`, `file_manifest`(상대 regular file별 SHA256), `device`(cpu/mps), `dtype`(float32), `max_pair_tokens`, `batch_size`(1..8), `timeout_seconds`(1..300). 기본 cpu/float32/512/1/120. BGE max_pair_tokens는1..8192, mMiniLM은1..512이며 실제 tokenizer/model 한도도 검사한다. 실제 revision과 파일 hash는 사용자가 준비한 exported local snapshot을 고정한다. 0 revision/빈 manifest/EXAMPLE path는 preview만 허용하며 모델 실행 불가다. 준비 검토에 fictitious revision을 실제 모델로 넣지 않는다.

P010의 실제 retrieval lock과 worker 정책을 재사용한다. 모델별 profile identity에는 HF ID/revision/파일 hash, SDK 버전, dtype/device, pair 처리 정책, raw-logit scorer 버전을 포함한다. batch/timeout 같은 실행 설정도 결과에 기록하되 모델 내용을 바꾸는 설정과 구별한다. 최대100파일/4GiB, nonsymlink self-contained local 디렉터리, safetensors만 허용하고 외부 경로/custom code/pickle은 거부한다. 기존 P010 모듈 whitelist를 모든 arbitrary CrossEncoder 모듈에 넓히지 않는다.

실제 SDK는 torch CrossEncoder, local_files_only=True, trust_remote_code=False, token=False, offline 환경이다. 두 모델의 실제 config architecture/num_labels=1을 확인하고 모델 head를 임의 새로 초기화해 맞추지 않는다. `activation_fn=Identity`, apply_softmax=False, prompt 없는 query/passage pair로 raw 단일 logit을 얻는다. tokenizer pair special tokens를 포함하여 truncation=False로 먼저 길이를 재고 초과 pair IDs를 보고한 뒤 질문 전체를 실패시킨다. 기본 SDK longest_first truncation에 의존하지 않는다. 임의 청크 잘라내기/요약/제외/재청킹은 없다. 실행한 정확 pair token 수와 적용 한도·전처리 hash를 남긴다.

요청별 소유 subprocess 한 개, 질문/모델 순차 실행, timeout 시 해당 worker만 종료·종료 확인. 기존 사용자 서버는 건드리지 않는다. retry0, 저장 실패 뒤 재계산0. pair 수·query 수·worker 수·모델 load/score/전체 지연, peak RSS와 관측 방법/한계를 별도로 보고한다. 매번 새 worker이므로 이를 warm model benchmark라고 부르지 않는다. 미측정 값은 null이다. UI/CLI는 `--execute-reranking`과 서버 허용으로 reranker 계산을 구분하고 embedding/generation 허가를 재사용하지 않는다.

## 고정 후보 artifact

`rag-lab candidates --build BUILD --result RESULT --question-id ID --n N --out OUT`는 저장된 P010 answer/검색 결과와 build를 검증해 후보를 고정한다. 모델/embedding/LLM 호출0. N1..100 기본20. result.query_hash와 질문, source/chunk/index fingerprint, effective settings, branch trace를 확인한다. 완전한 검색 결과이면 generation 실패 여부와 무관하게 후보 고정 가능하다. 검색 실패/trace 없는 과거 artifact는 명시 오류다.

P010 trace의 BM25/Dense branch를 사용한다. Hybrid는 저장 rrf_k와 기존 RRF 계산으로 전체 결합 순위를 복원한다. 복원한 top_k가 원 candidates와 일치해야 한다. 최종 contexts나 예산 제외 후 목록에서 N을 만들지 않는다. 원 검색 candidate_k>=N을 요구하고 미충족이면 별도 충분한 검색을 먼저 하도록 안내한다. source/정상 BM25 결과가 작아 실제 후보가 N보다 적으면 actual_n/shortage_reason을 기록하며 빈 후보도 실패와 구분한다.

candidate artifact v1은 source/chunk/index/query identity, question_id/question, retrieval settings/원 결과 fingerprint/실행 종류, requested_n/actual_n/candidate_depth, 원 순서의 candidate rows를 가진다. 각 행은 chunk_id/original_rank/retrieval_score/text/text_hash/document_id/start/end/pages/heading_path. canonical 원문 snapshot과 전체 corpus chunk ID·구간·본문 hash를 포함해 외부 경로 없이 검증/원문 표시/qrels unknown ID 검사/재생이 가능하게 한다. vector/embedding 모델 파일은 복사하지 않는다. 원문·전체 청크·후보의 hash와 구간 일치를 로드마다 검증한다.

manifest는 immutable/no-clobber. candidate_fingerprint는 질문·출처·검색 설정·순서·본문 hash를 묶는다. 같은 후보를 off/on 및 모델마다 읽고 비교 중 재검색/재임베딩/재파싱하지 않는다. 같은 글자라도 source/query/revision이 다르면 같은 paired 비교로 묶지 않는다. 원 artifact를 overwrite하거나 qrels를 추가해 다시 봉인하지 않는다.

## 재정렬·문맥 선택·생성

`rag-lab rerank --candidates DIR --method none|cross-encoder --profile FILE --top-k K --context-budget-chars B --out OUT [--execute-reranking]`. profile은 cross-encoder에만 필수이고 none에서 주어지면 오류다. K1..requested_n 기본5(기본값 적용 후에도 범위 검사), B1..64000 기본4000. 실제 후보가 K보다 적어도 빈 순위 자리를 만들어 넣지 않는다. none은 원 순위, worker0. cross-encoder는 미허용/미설정이면 preview, 예상 pair 수와 미실행 이유를 표시하고 score0/가짜 순위를 생성하지 않는다.

모든 실제 후보의 score를 한 번씩 받는다. 개수/차원/ID mapping/finite를 확인하고 누락/NaN/unknown/중복이면 해당 질문 전체 실패다. raw score 내림차순, 동점은 original_rank, 이후 chunk ID 순. 반올림은 표시만. 모델 간 raw score를 합치거나 확률로 동일시하지 않는다. 전체 N개 점수/순위, 전후 rank/delta, top K, whole-chunk 문자 예산에 들어간 contexts/제외 사유를 모두 저장한다. 예산 초과 chunk는 자르지 않고 제외하며 top K 밖에서 보충하지 않는다. 점수 임계값 기반 자동 답변 보류는 이번 범위가 아니다.

`rag-lab answer-from-rerank --run DIR --llm-config FILE --out OUT [--execute]`는 실제 완료된 none/리랭킹 결과만 받아 후보/순위/선택 문맥을 검증하고 기존 provider preview/invoke·ID-only citation 검증을 재사용한다. rerank preview/failed는 생성 입력으로 사용할 수 없다. 재검색·재임베딩·재리랭킹0. 기본 generation preview, 별도 --execute에서만 생성 최대1회. 문맥이 비면 보류/0호출. 생성 실패가 검색 비교 점수나 원 rerank artifact를 바꾸지 않는다. 결과에 parent rerank/candidate fingerprint, 실제 messages hash와 소스 인용을 남긴다.

## 비교·보고서·UI

`rag-lab rerank-compare --candidates-set FILE --variants FILE [--qrels FILE] [--facts FILE] --out OUT [--execute-reranking]`를 제공한다. candidates-set v1은 중복 없는1..20개 question_id와 candidate 경로, variants v1은2..4개 고유 id/label과 method/profile/top_k/context_budget_chars를 가진다. none 기준선을 정확1개 포함한다. 모든 variant의 K/B는 같아야 하며 후보 집합과 question hash가 같음을 사전 검증한다. 질문별 candidate는 같은 source/chunk identity, 질문 세트 hash를 묶고 다른 corpus끼리 macro 비교하지 않는다. 경로는 CLI 설정 파일 기준으로 해석하고 UI에서는 등록 opaque ID만 받는다.

최대3모델×20질문×100후보=6000 scoring pairs, 실제 fixture 검증은 작은 표본으로 제한한다. 설정·정답 입력은 worker 시작 전 검증한다. 질문별 실패/미실행/빈 후보를 행으로 남긴다. 각 model과 none의 지표 차이는 양쪽 유효인 같은 질문만 계산하고 paired-valid/전체/실패·제외 이유를 표시한다. 성공 행만 남겨 전체 개선처럼 표시하지 않는다. 질문별 개선/악화/동일과 예산 전후 차이를 보여준다. 전체 지연은 저장 원 검색 지연과 새 리랭킹 지연을 분리하며 서로 다른 실행시점/캐시 조건을 같은 동시 측정처럼 표시하지 않는다.

`rag-lab rerank-report --run DIR --out OUT`는 저장된 후보/score/rank/qrels/facts의 검증·재계산으로 HTML/Markdown 요약을 만든다. SDK import/모델/키/네트워크0, 원 결과 불변. HTML은 입력 텍스트를 escape하고 스크립트 명령으로 실행하지 않는다. 누락 파일·변조는 오류다. 요약과 개별 결과의 지표/분모가 같아야 하며 결과 봉인 전에 지표를 기록한다.

UI startup `--reranker-config` 최대4, `--allow-reranking-execution` 기본false를 추가한다. 기존 source/build/answer registry에 candidate/rerank/rerank-comparison 유형과 원문 추적을 연결한다. 고정 후보 생성→none/모델 비교→전후 순위·원문·지표/비용→선택 결과로 generation preview/선택 실행이 실제 코어로 이어져야 한다. Qrels/facts는 서버 측 사전 등록된 파일만 선택하고 미등록 시 N/A다. arbitrary 경로/model/custom code를 웹에서 받지 않는다. single job/idempotency/restart interrupted와 기존 권한은 보존한다. 미설정·미허용·미실행과 낮은 점수를 구분한다. CLI에는 가능한데 화면 버튼만 있는 기능으로 끝내지 않는다.

새 학습 가이드 `docs/learning/rag-package/reranking.md`와 stage의 설정 예시/실습/manifest를 갱신한다. 원 score와 순위 차이, 후보 N과 K, 검색 누락은 리랭커로 복구 못함, qrels와 GT 구분, 길이 초과 복구, 순차 worker 비용, fake/tiny/실제 품질 증거 차이를 예시로 설명한다. 공개 모델 export/profile 준비 안내는 P010을 연결하고 실제 경로·hash를 사용자가 채워야 하는 부분을 명시한다.

## 지표·fact/span 정책

P010 chunk qrels schema/산식을 계승한다. source/chunk/questions fingerprints와 전체 corpus ID를 대조하며 grade0/1/2, 관련=grade>0, judgments_complete=true만 미기재 청크0으로 처리한다. incomplete는 지표 N/A다. Precision@K=hits/K, Recall@K=hits/전체 관련, MRR=첫 관련 rank 역수, nDCG는 전체 corpus qrels 상위K의 IDCG를 사용한다. 후보 밖 정답을 분모에서 제거하지 않는다. 후보N Recall, 최종K 지표, 예산후 전달근거 recall을 따로 표시한다. 예산후 precision을 표시한다면 분모는 실제 전달 수로 명시하고 Precision@K와 같은 이름으로 쓰지 않는다.

관련0 질문은 Recall/MRR/nDCG N/A/no_relevant, Precision은 별도 no-answer 그룹이다. answerable/no-answer/failed/incomplete 집계를 분리하고 macro 값마다 유효·제외 수를 남긴다. empty 후보의 answerable 질문은 hits0으로 유효0점이며 모델 실패와 다르다. Faithfulness/Correctness는 evaluator_not_connected로 N/A다. 실제 정답 의미를 모델 score만으로 판정하지 않는다.

optional facts v1 필드: schema_version,source_fingerprint,questions_hash,offset_unit="unicode_codepoint",questions. 질문별 question_id/required_facts, fact별 fact_id/alternatives, alternative별 spans, span별 document_id/start/end/quote. fact ID는 질문 안 고유. alternative의 spans는 AND, alternatives는 OR다. canonical NFC/LF `[start,end)`와 정확 quote를 검증하고 page는 원문 mapping에서 유도한다. question set 전체를 명시하고 empty required_facts는 no_required_facts/N/A. 질문100facts, fact4alternatives, alternative8spans 상한. source/문서/범위/중복 JSON key/추가필드/타입 오류는 거부한다.

동일 document 안에서 선택 chunk 구간 union으로 span을 전부 덮어야 충족이다. 서로 다른 문서를 합치지 않는다. 모든 span을 충족한 alternative가 하나라도 있으면 fact1회, 중복 chunk로 추가 가산 없음. 후보N/최종K/실제contexts 각각 fact_recall=충족필수fact/전체필수fact와 all_required를 기록한다. 질문별 fact macro와 전체 충족fact/전체fact인 micro는 다른 이름으로 표시한다. zero-fact 질문은 두 집계의 분모에서 제외하며 수를 남긴다. 모델 payload에는 query/candidate text/profile만, qrels/GT/facts/기대순위·정답은 전달하지 않는다.

## 독립 검증과 완료 증거

- 수기 순위 fixture: corpus qrels a2,b1,c0,d2; 후보[a,c,b],K2. none precision.5/recall1/3/MRR1/DCG3, rerank[a,b,c] precision1/recall2/3/MRR1/DCG3+1/log2(3), 양쪽 IDCG3+3/log2(3). 후보 recall은 둘 다2/3. d 누락 분모 유지. score동점/음수/반올림/중복/NaN/count/빈후보/K/예산 경계 포함.
- span fixture: f1=d[0,5) AND d[10,15), f2=d[20,25) OR e[0,5). d[0,3),d[3,5),d[10,15)→1/2,false; 중복은 불변; e[0,5)추가→2/2,true; 예산에서 d[3,5)제외→1/2,false. 다른문서 구간 병합 금지. 코드 구현으로 기대값을 만들지 않고 독립 정답표를 보관한다.
- snapshot/질문/순서/본문/qrels 변조·stale·no-clobber·replay0모델, candidate 생성0검색, none0worker, 실제worker pair순서/길이초과/timeout/부분결과/잘못된head 검증. score fixture에는 deterministic injection 라벨, production CLI에는 injection 옵션 없음.
- 실제 SDK tiny locally generated sequence classifier(≤10M parameters/512MiB)를 safetensors로 저장해 worker 호출/score와 직접 logits 비교/전처리 경계/종료를 확인한다. SDK 버전 변경 필요 시 원인과 lock을 설치 전에 기록하고 P010 회귀를 확인한다. 기존 lock을 조용히 교체하지 않는다.
- qrels 미제공/불완전/no-answer/한쪽실패의 집계 분모, summary/detail/replay 동일성, GT 누출 없는 worker payload, generation preview와 fake provider3종 citation/invalid ID/빈근거·실패 경계를 확인한다. actual provider 호출0.
- source 없는 새 venv에 wheel 설치, SDK lock과 stage 실습 CLI·보고서·UI asset 확인. 허용 브라우저에서 등록 합성 후보로 none/on·모델 선택·전후 순위·원문/예산·비교/오류·generation preview·좁은 화면/키보드 확인. 정책 거부는 우회하지 않고 미완료로 남긴다.
- 기존 package/harness 필수 회귀, 단계/GT/P013 보류·grant/P029 미완료 hash 보존, 소유 프로세스 종료, exact adoption/guard/queue, `docs/verification/p020/` 커밋 증거와 정상 personal/dev push. 라이브 품질 미검증·지원환경·검증 종류를 완료 보고에 명시한다. 지표가 개선될 것을 완료 조건으로 강제하지 않는다.
