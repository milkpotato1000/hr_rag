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
