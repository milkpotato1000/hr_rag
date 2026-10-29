# P007 상세 설계 — 다섯 청킹 방식과 검색 비교 UI

상태: **준비 완료**. 2026-10-29 P016 단일 규정집 완료와 제한된 사전 검증을 반영했다. [P007](../planning/plans/P007.md)과 [준비 검토](../planning/reviews/P007-readiness.md), [고정 실행 spec](../planning/specs/P007-experiment-draft.json)을 정확히 채택한 뒤 dev가 구현한다. 파일명의 draft는 이전 경로를 유지한 것이며 JSON status=READY_FOR_DEV_ADOPTION이 현재 상태다. 준비 검증은 전체 청킹/검색/UI 구현 완료가 아니다.

## 1. 기반과 입력 고정

P016 완료 dev commit은 `4cdee6f9583c899d76e95237af8b5de8d77d8012`다. source-v4 단일 규정집은 PDF23페이지, 본문35,477자·canonical38,582자,6장15절57조항이다. 인계62파일·완료증거10파일·미리보기23장 hash를 확인했다. [source profile](../planning/reviews/p007/source-profile.json)의 완료 commit/hash에 고정하며 P015/source-v3는 보존 기준선이다. 검색 결과를 보고 원문을 바꾸지 않는다.

작업은 P015의 `2. Document Chunking/`에서 계속한다. P016의 단일 규정집 PDF·canonical/page map·policy-map·인계 manifest를 읽고 원문을 수정하지 않는다. 실험 설정에 corpus/input manifest hash를 저장하고 불일치는 재사용 거부다. 같은 PDF의 Markdown 사본을 중복 입력하지 않는다. 표지/페이지 번호/가상 안내도 canonical의 일부로 보존한다. 소스 수정이 필요하면 원문 버전 변경과 실험 재시작을 plan에서 따로 판단한다.

P012의 `1. Naive RAG/variants/langchain/`에서 scripts/{chunk_documents,document_common,run_bm25_baseline,evaluate_retrieval,build_dense_index,dense_retrieval,runtime_common,generation,serve_compare}.py, 필요한 import 의존 파일, 고정 lock, 관련 테스트, web_compare UI 구성/스타일을 복사·선별한다. PDF/추출 도구는 P015 사본을 재사용한다. 새 기능은 새 단계 안에서 수정하고 원래 생성/비교 UI·15청크/source-v2·색인/모델/증거는 보존한다. 복사 후보28파일과 정적 local import 연결은 [copy candidates](../planning/reviews/p007/copy-candidates.json)에 고정했다. 기존 새 단계의 document_common.py/test_documents.py는 내용이 달라 덮어쓰지 않고 호환성을 통합한다. 정적 목록은 런타임 독립 실행 검증을 대신하지 않는다. 환경·모델 가중치·캐시를 소스처럼 복사하지 않는다.

기존 BM25와 Dense는 `title + LF + text`를 검색 입력으로 사용한다. **이번 실험의 공통 입력은 `text`만**으로 고정한다(`text_version=canonical-slice-only-v1`). 제목/조항명은 표시 메타데이터다. 실제 canonical 본문에 있는 제목은 그 위치에 남는다. 모든 방식/검색기에 같은 규칙을 적용하고 새 색인 manifest에 기록한다. 이전 색인을 그대로 재사용하지 않으며, 이 변경을 청킹 성능 개선으로 주장하지 않는다. 제목 보강 비교는 이번 기본 실험에서 제외한다.

source-v4는 document_id 하나의 연속 canonical이며 주제 장6개는 section metadata다. 목차와 본문 제목을 구분하고 전역 offset을 유지한다. UI는 통합 목차→장/절→페이지를 탐색하며, 장을 가상 문서로 분리해 문서당 window 제한을 우회하지 않는다. 전체 문서 기반 호출 예산은 아래에 고정하고 장별 경계/회수 통계도 별도 보고한다.

## 2. 원문 단위·경계와 공통 불변 조건

offset은 NFC/LF canonical의 Unicode code point `[start,end)`이며 바이트/토큰/PDF 좌표가 아니다. 모든 청크 text는 canonical의 정확한 연속 slice다. 문서 간 결합·요약·문장 재정렬·제목 복제를 하지 않는다. 비겹침 기본 분할은 `[0,len(text))`를 빈틈없이 덮고 끝에서 종료한다. 공백만인 범위는 별도 skipped 기록으로 남기며 방출 청크+skipped 범위가 전체를 덮어야 한다.

후보 단위 `boundary-map-v1`은 [프로파일 스크립트](../planning/reviews/p007/profile_source.py)와 [고정 경계 map](../planning/reviews/p007/boundary-map.json)을 따른다. `\n\s*\n` 문단 끝, 실제 section map heading의 끝(뒤따르는 공백 포함), `.?!。！？` 뒤가 공백/문서 끝인 문장 끝(뒤따르는 공백 포함)을 경계로 사용한다. 공백을 삭제하지 않으며 PDF의 단순 줄바꿈·목차 항목은 별도 제목 경계로 만들지 않는다. 숫자 사이 소수점은 뒤가 공백이 아니므로 경계가 아니다. 긴 단위는400자마다 임시 경계를 추가하고 forced_atom_split을 기록한다. 순서 정렬된 구간에 u00000부터 ID를 부여한다. 실측630단위·강제 단위분할0건이다. 언어학적 문장 분석기가 아닌 휴리스틱이며 약어/줄바꿈 한계를 남긴다. dev는 독립 fixture와 고정 map 재현을 함께 검증한다.

source map은 각 청크의 기본 start/end와 overlap 확장 start/end, 실제 페이지 교차 구간, 단위/조항 ID, 원문·추출 hash를 보존한다. 페이지 사이 구분자에는 가짜 페이지 번호를 부여하지 않는다. 최초 복사 해시와 현재 결과 해시를 구분한다. 청크 ID는 문서/hash·알고리즘 버전·설정·실제 범위에 기반하며 같은 검증된 분할 결과를 재생할 때 동일하다. 모델을 새로 실행해 경계가 달라지면 다른 artifact/hash다.

## 3. 알고리즘과 14개 초기 설정

| 방식 | 기본 분할 계약 | 실험 설정 수 |
| --- | --- | --- |
| fixed | P006 방식 그대로 start+=size-overlap; 마지막 end=len이면 종료 | size 200/400/800 × overlap 0/20% = 6 |
| recursive | 최대400자 안에서 문단 끝 → 문장 끝 → 공백 끝 순으로 가장 오른쪽 경계를 선택. 없으면400자 hard cut. 다음 기본 구간은 직전 end에서 시작 | overlap 0/80자 = 2 |
| structure | 검증된 실제 제목/장/절/조항 시작 경계마다 기본 분할(목차 제외). 긴 조항만 recursive 최대400자로 분할. 짧은 조항을 다른 조항과 합치지 않음. 문서 앞부분도 별도 구간 | overlap 0/80자 = 2 |
| semantic | 공통 단위 임베딩의 인접 cosine distance가0.25 이상이면 현재 chunk가100자 이상일 때 경계. 최대400자를 넘기기 직전 단위 끝에서 강제 분할; 마지막100자 미만은 그대로 표시 | overlap 0/80자 = 2 |
| llm | 아래 window 안의 단위 ID 끝에서만 경계 선택; 기본 chunk 최대800자, 권장200~400자. 짧은 마지막/단일 단위는 허용하고 기록 | 같은 경계의 overlap 0/80자 = 2 |

recursive/structure/semantic/llm의 overlap은 **기본 분할 뒤** 각 구간의 시작을 최대80자 앞으로 확장하되 `max(직전 기본 구간 start, 현재 start-80)`로 제한한다. 첫 구간은 확장하지 않는다. 확장된 구간 최대 길이는 기본 최대+80이다. 문장/조항 경계를 넘어갈 수 있으므로 UI에 그 사실을 표시한다. fixed의 내장 sliding overlap과 의미가 다르며 결과 길이/중복량을 함께 비교한다.

구조 경계는 canonical에 실제 있는 제목/조항으로부터 얻는다. P016 편집 원문의 제목을 근거로 canonical exact match·페이지/offset을 대조해 section map을 동결한다. 자동 탐지/수동 대조 여부를 명시하고 탐지 실패를 의미 기반 알고리즘의 효과로 해석하지 않는다. 메타데이터에만 있는 제목으로 경계를 만들지 않는다. 특정 규정의 예외를 잘 회수하도록 정답을 보고 재배치하지 않는다.

semantic은 기존 `bge-m3:567m`, 1024차원 벡터로 계산한다. `distance=1-dot(a,b)/(norm(a)*norm(b))`이며 유한값/0벡터를 검증하고 반올림 값으로 threshold를 판정하지 않는다. 길이 우선 조건을 먼저 적용하고 threshold와 같으면 분할한다. 문서 순서대로 계산하며 tail 병합은 하지 않는다. 단위 임베딩 cache는 model digest·text hash·입력 규칙으로 키를 만들고 구축 비용과 cache hit를 별도 기록한다.

14개 설정을 이 corpus의 최초 비교 그리드로 동결한다. fixed의 실측 청크 수는200/0=193,200/40=241,400/0=97,400/80=121,800/0=49,800/160=61이다. 나머지 방식의 실제 경계/품질은 미실행이며 모두 같은 경계가 나오는 경우도 결과다. 실험 후 추가 설정은 새 experiment version으로 분리한다.

## 4. LLM 경계 선택·모델·예산

기존 로컬 lock과 실제 /api/version/tags/show를 대조했다: Ollama0.40.8, `qwen3:4b` digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`, stream=false,think=false,temperature0,seed42,num_ctx8192,num_predict1024. BGE digest는 `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`다. [runtime metadata](../planning/reviews/p007/runtime-metadata.json)와 [probe results](../planning/reviews/p007/probe-results.json)를 보존한다. 기존 generation.py/답변 lock을 바꾸지 않고 별도 chunking-model-lock.json/adapter를 만든다. 새 모델 다운로드/교체는 포함하지 않는다. 실행마다 pinned metadata를 검사한다.

모델 입력은 [prompt contract](../planning/reviews/p007/prompt-contract.json)의 정확한 prefix+schema+unit JSON을 담는 단일 user 메시지다. system/tools/images/대화 history는 사용하지 않는다. source unit fields는 id,start,end,text이며 JSON 직렬화도 고정한다. 문서는 데이터로 취급하고 질문/정답/rubric/검색 결과를 입력하지 않는다. unit ID만 반환하고 내용을 재작성하지 않는다. 내부 추론 전문은 요청/수집하지 않으며 message.content와 완료/사용량·검증 메타데이터를 기록한다.

응답은 `{"end_unit_ids":["u...",...]}` 하나의 필드만 허용한다. schema는 additionalProperties=false, 배열 minItems1/uniqueItems=true, item enum=해당 window IDs다. Python이 목록의 존재·타입·중복·오름차순·마지막 ID·최대800자·모든 단위 포함을 별도로 검증한다. 알 수 없는 ID, 누락된 마지막 ID, 빈 응답/중복 JSON key/잘린 응답은 실패다. 단위가 최대로400자이므로 최대800자 내 분할은 가능하다. 최소 길이는 권고값으로 길이 미달을 별도 기록하고 내용을 늘리지 않는다.

window는 순서대로 최대1200 canonical 문자·최대20단위까지 묶고 단위 사이를 끊지 않는다. 첫 실험에서는 window overlap0, window 끝을 강제 경계로 유지한다. 합치기/재분할 없이 window 결과를 이어 붙여 전체 coverage를 검증한다. 이 제한의 인위적 경계 개입 수를 표시한다. 원문 overlap80자는 모델 호출 이후 적용하므로 추가 추론은 필요 없다.

1,200문자는 토큰 수가 아니다. [입력 예산 근거](../planning/reviews/p007/input-budget.json)는 현재 GPT2 byte-BPE/qwen2 tokenizer·단일 user·고정 template에 한해 `UTF8(content) + UTF8(template 전체) + UTF8(schema) +64`를 보수적 입력 토큰 상한으로 사용한다. schema는 content에도 들어 있으므로 중복 예산이며 byte BPE 병합은 byte symbol 수를 늘리지 않는다. 현재 최대6,510+출력여유1,024=7,534로8,192 안이다. 정확 tokenizer count가 아니다. 모델/template/입력 형태가 달라지거나 상한을 넘으면 budget_unverified로 거부하고 조용히 truncate하지 않는다. 실제 prompt_eval_count1492~1578 관측만으로 무절단을 증명했다고 주장하지 않는다. 최초1,600자 후보의 상한 초과는 별도 실패 기록에 보존했다. done=true/done_reason=stop을 검사하며 length/불완전 응답은 실패다.

전체 문서를35windows로 처리한다. 35×3독립반복×최대2시도=210요청, 준비 검증에서 사용한3회와 dev 호환 smoke 최대6회를 합쳐 LLM 전체 상한219회다. 요청당90초, 전체 모델 작업 wall time120분 중 먼저 도달하는 제한에서 중단한다. 자동 재시도는 동일 입력1회(2초 지연),동시 모델 작업1이며 모든 실패와 실제 서버 호출/시간을 ledger에 누적한다. 이미 사용한 준비3회를 ledger 초기값에 반영하고 캐시 재생은 호출로 세지 않는다. 초과/변경된 corpus는 누락 없이 preflight 실패다. 현재 표본9.17~19.26초/요청은 전체 실행 시간 보장이 아니다.

전체 corpus 3회 독립 반복(seed/모델/입력 동일, 응답 cache 사용 금지)을 실행한다. 첫 유효 corpus 실행을 검색 비교 대표로 고정하고 성능이 좋은 반복을 사후 선택하지 않는다. 첫 실행이 실패하면 그 실패를 보존하고 다음 유효 실행을 선택한다. 모두 실패하면 llm은 비교 실패로 기록하며 성공한 것으로 대체하지 않는다. 수동 수정·fixed fallback은 허용하지 않는다. 임의 fake 응답은 독립 테스트에만 쓴다.

제한된3회 probe에서는 모든 단위 끝을 선택하는 과분할 양상이 관찰됐다. 유효 형식이므로 임의 병합/fallback으로 숨기지 않고 단위 수 대비 청크 수·권장200자 미만 비율과 원문 경계 분포를 보고한다. 특정 방법의 품질 우위는 완료 조건이 아니다.

반복 안정성은 문서별 모델 선택 내부 경계 집합 B의 exact 일치율 및 쌍별 Jaccard `|Bi∩Bj|/|Bi∪Bj|`를 보고한다. 두 집합이 모두 비면1, 한쪽만 비면0; 문서 시작/끝·강제 window 경계는 제외하고 별도 집계한다. 실패 반복은 안정성 점수 N/A와 실패율로 표시하며 성공 쌍의 분모를 숨기지 않는다. 3반복의 청크 수·길이 분포와 캐시 재생 결과도 구분한다. 이것은 작은 세트의 관찰이지 모델 결정성 보장이 아니다.

## 5. 검색 정답과 평가 산식

검색용 데이터는 [고정 dataset](../planning/specs/P007-retrieval-dataset.json)의 source-v4 exact quote/offset/hash와 정책 inventory ID를 따른다. Codex 원문 대조이며 P013의 사람 승인 Reference Claims가 아니다. 질문은 필요한 fact를 모두 충족해야 하고, 각 fact는 하나 이상의 evidence_sets 중 하나의 모든 span을 회수하면 충족한다(집합 간 OR,집합 안 AND). 서로 다른 대체집합의 일부만 섞어 성공 처리하지 않는다. 현재37fact는 각각 한 집합이며 동일 의미의 검증된 대체 위치를 추가할 때 새 dataset version을 만든다. 주석은 등록한 근거 위치의 회수 평가이며 모든 의미상 동등 표현을 완전하게 열거한 정답이라는 주장은 하지 않는다.

질문38개: tuning26개(기존14 재대조+신규절차12),holdout12개(답변가능10/불가2). 신규 tuning/holdout은 조항 그룹이 겹치지 않으며 holdout에는 장 간 복수 근거 질문을 포함한다. 기존 질문은 관찰된 자료로 유지한다. 정답 없는 질문은 원문 범위 내 정보 부재이며 제도 자체의 부재가 아니다. holdout은 설정 동결 전에 커밋하되 tuning 지표/기본 UI 예제/후보 선정에는 제외한다. 처음 평가·공개한 이후에는 관찰된 자료가 되며 같은 holdout으로 반복 최적화하지 않는다. 같은 Codex가 작성·대조했으므로 독립 사람 검증/일반화 성능을 주장하지 않는다.

검색은 BM25와 Dense를 **별도 고정 실험군**으로 수행한다. BM25 k1=1.2/b=0.75, 기존 unicode-word-v1 tokenizer를 재사용하되 text-only를 적용한다. Dense는 기존 BGE/Qdrant cosine를 사용하고 동점은 chunk_id 오름차순으로 재정렬한다. 문서/모델/설정/query hash와 index fingerprint가 맞는 색인만 읽는다. UI 임의 질문 최대2000자, top-k1~20(기본5); 보고 K=5/10/20이며 각 corpus가 작으면 실제 반환 개수를 함께 표시한다.

- **Fact recall@K:** top-k 청크의 document별 원문 범위 합집합이 각 fact의 evidence_sets 중 하나의 모든 span 전체를 덮는지 확인하고, 충족 fact 수/질문의 필수 fact 수를 계산한다. 분할된 사실을 여러 청크가 함께 덮는 경우도 인정한다. 중복 청크/overlap으로 분자를 늘리지 않는다.
- **Full evidence success:** 질문의 모든 필수 fact 충족 여부(0/1). **부분 coverage:** 각 evidence set 내부 span 합집합 길이에 대한 회수 교집합 비율을 구한 뒤 fact별 최댓값을 사용한다. 문서별 범위를 분리하고 같은 fact 내부 겹침을 먼저 합친다. 주 지표와 부분 coverage를 서로 대신하지 않는다.
- **보조 chunk qrels:** 한 청크가 필요한 fact 하나의 evidence set 하나를 완전히 포함하면 grade2, 그렇지 않고 필수 span의 공백 이외 문자를 하나 이상 포함하면 grade1, 나머지0. chunk ID는 전략별 source map에서 다시 생성한다. 여러 청크 결합에만 의존하는 fact는 grade2가 없을 수 있어 fact recall이 주 지표다. 모든 청크의 grade를 계산해 분모를 고정한다.
- **P@K:** top-k 중 grade>0 수/K(결과 부족 슬롯은0). **R@K:** top-k grade>0 수/corpus 전체 grade>0 수. 분모0이면 N/A. **MRR@K:** 첫 grade>0의 역순위, 없으면0. **nDCG@K:** gain=`2^grade-1`, discount=`log2(rank+1)`, IDCG는 corpus 전체 grade 내림차순 상위K; IDCG0이면 N/A. 순위1부터 계산한다. 전략별 qrels 분모가 다르므로 이 보조값만으로 우승을 정하지 않는다.
- 답변 불가 질문은 fact recall/qrels 지표 분모에서 제외하고 검색 결과/점수·길이·분량을 관찰한다. 이 단계는 생성 보류/답변 정확도를 평가하지 않는다. 임의 사용자 질문 또는 정답 미연결이면 N/A, 판정 오류도0점으로 위장하지 않는다.
- **분량 기준 비교:** 동일 retrieval top20에서 예산400/800/1600문자로 별도 측정한다. 순위대로 whole chunk를 검사하고 남은 예산에 안 맞으면 제외하되 다음 후보를 계속 검사한다. 청크를 잘라 넣거나 겹친 문자량을 할인하지 않는다. 선택/제외 이유·실제 사용량을 기록하고 fact recall을 다시 계산한다. 이 선택은 `context_budget_simulation`이며 아직 LLM에 전달한 문맥이라고 표시하지 않는다.

유효 질문별 macro 평균을 기본으로, 전체 충족fact/전체 요구fact인 micro를 함께 제공한다. N/A/오류/답변 불가 수와 적용 분모를 보고서에 표시한다. “누락 없는데 회수 실패”, 중복으로 점수 증가, 다른 문서 offset 혼동, 하나의 fact의 두 span, 결과<K, IDCG0을 독립 기대값으로 검증한다.

## 6. 실험량·선정·비용

tuning14설정×2검색기×26질문=728 ranking,선정 뒤 holdout 기준선/후보 최대2설정×2검색기×12질문=48 ranking으로 총776개다. 후보=기준선이면 중복 생략한다. K/문자 예산 지표는 같은 ranking에서 파생한다. 지연 측정은 최대3회(기본 포함2328 ranking 요청),실제 cold/load 여부와 설정 순서를 기록한다. 구축 시간·색인 크기·검색 지연을 분리한다.

원문 단위/설정별 청크 최대1000,embedding batch32·timeout60초·동일 item 최대2시도,전체 input item 누계32000(준비2item 포함)·wall time30분을 상한으로 둔다. 14설정×1000chunk×2시도+630unit×2+38query×2=29336item보다 여유가 있으며 중복 overlap/캐시 재사용 여부를 ledger에 기록한다. embedding은 truncate=false,유한1024차원/0벡터 거부,모델/version 변경 거부다. 메모리 총량16GiB는 확인했으나 가용/peak 메모리 보장이 아니므로 실제 peak/오류를 기록하며 자원 실패 시 자동 상한 확대 없이 실패한다. 런타임 색인은 한 번에 하나씩 처리하고 누적 ledger를 재시작으로 초기화하지 않는다.

기준선은 fixed400/80이다. 후속 P013 비교 후보는 tuning Dense fact recall@5 최댓값, 동점은 emitted/unique 문자비가 낮은 것, 다음 구축시간이 짧은 것, 다음 config_id 사전순으로 정한다. BM25 결과는 별도로 보고한다. 반복 모델 경계는 앞 절의 대표 실행만 사용한다. holdout은 선정 후 기준선/후보를 확인하며 holdout 점수로 재선정하지 않는다. 유효 후보가 기준선을 넘지 못하면 기준선을 유지한다. 전체 그리드 결과와 실패를 삭제하지 않는다.

## 7. 저장 계약·CLI·UI/API

공통 라이브러리를 CLI와 서버가 호출한다. 예정 CLI는 `chunk_documents.py --documents <manifest> --config <json> --output-dir <new-dir>`, `run_chunking_experiment.py --spec <json> --output-dir <new-dir>`, `serve_chunking.py --port 8003`이다. 이 명령들은 dev 구현 대상이며 plan 준비에서 이미 동작한다고 주장하지 않는다.

고정 설정/데이터는 `experiments/p007/`(spec, 질문/정답, 동결·출처), 런타임 색인은 `.runtime/indexes/<fingerprint>/`, 보존 산출물은 `artifacts/<run_id>/`에 둔다. 파일을 덮어쓰지 않는다. metadata와 JSONL 원문은 UTF-8, JSON NaN/중복키를 거부한다. manifest schema_version1에는 corpus/input hashes, code/algorithm version, config, model/runtime lock hashes, parent run IDs, status, output hashes, timings/counts를 둔다. status는 complete/failed/interrupted이고 실패 산출물은 성공 manifest/index로 게시하지 않는다.

각 성공 chunk run은 chunks.jsonl(기존 필수7필드), source-map.json, statistics.json, manifest.json을 제공한다. 모델 결과가 있으면 입력/prompt hash·원응답의 content·검증/경계·usage·retry ledger를 연결한다. ranking은 query_id/query_hash, run/index/config ID, retriever, ordered chunk IDs/scores, elapsed_ms를 가진다. evaluation은 dataset/version/hash와 metric denominator/status를 별도 저장해 검색기 입력과 분리한다.

UI는 원문 → 청킹 실험 → 검색 비교의 세 영역이다. 기존 P012 스타일/키보드 접근성을 재사용한다. PDF는 allowlist된 원본 보기/다운로드와 페이지별 검증된 미리보기([preview manifest](../planning/reviews/p007/preview-manifest.json)의 P016 검증PNG23장 복사, pdftoppm26.08.0/92dpi 출처 기록; 런타임 렌더러 의존 없음), 옆에 canonical 구간을 표시한다. 청크 클릭은 canonical 범위/페이지로 이동한다. 문자 offset을 PDF 좌표 하이라이트처럼 그리지 않는다. 이미지/텍스트와 별도로 PDF 원본 링크를 제공한다.

| API | 요청/결과 의미 |
| --- | --- |
| GET /api/corpora | 등록된 corpus ID/version/hash·fixture 상태·문서 목록 |
| GET /api/documents/{id}?corpus_id=... | 등록 문서의 페이지/추출본/section map; 원문·노트·정답 임의 경로 읽기 금지 |
| GET /api/documents/{id}/pdf 및 /pages/{n}/preview | manifest에 매핑한 PDF/PNG만 제공, traversal/미등록/symlink 거부 |
| POST /api/chunk-jobs | corpus_id, config, request_id, fresh(명시 bool); 명시 실행만202+job_id, 같은 request_id/같은 내용은 재사용, 내용이 다르면409 |
| POST /api/index-jobs | 완료 chunk_run_id, retriever, request_id; fingerprint 검증 후202 |
| GET /api/jobs/{id} | 상태/단계/진행/시간/호출량·오류/결과 참조; 폴링 자체는 실행하지 않음 |
| POST /api/search-comparisons | 같은 corpus의 준비된 A/B run IDs, retriever, question 또는 등록 query_id, top_k, budget_chars; 서버가 둘 중 한 질문 출처만 허용하고 비교 조건 일치 검사 |
| GET /api/runs/{id} 및 /export | versioned artifact/metrics를 읽고 같은 실행 결과를 다운로드 |

GET/방식 선택/새로고침은 모델을 호출하지 않는다. model/경로/원격 endpoint 임의 입력은 받지 않는다. JSON≤64KiB·허용 필드/type만 수용, 400입력/404미등록/409busy-or-stale/413크기/422설정·버전 오류를 구분한다. 수행 중 모델 오류는 job FAILED/provider 등 typed reason으로 반환한다. 응답은 `status`, `request_id`, `job_id/run_id`, `reason`, `data`를 상황별로 포함하며 내부 trace와 사용자 설명을 구분한다. 재시도 가능한지 실제 정책을 표시하고 자동 반복하지 않는다.

loopback127.0.0.1:8003을 기본으로 하며 점유 시 다른 서버를 종료하지 않고 명시 오류/다른 포트 지정으로 처리한다. 8001 기존 학습 서버를 유지하고 사용자 요청으로 종료한8000을 자동 재시작하지 않는다. Host/Origin 검증·CSP/nosniff·HTML textContent 렌더링을 계승하고 CORS나 임의 파일 제공을 열지 않는다. 다운로드 파일명/원문 text는 실행 코드가 아니다.

단계 단위 file lock으로 CLI/서버의 모델/색인 작업을 동시에1개만 수행하고 두 번째는409/busy다. job 상태는 QUEUED→RUNNING→SUCCEEDED/FAILED, 재시작 시 미완료는 INTERRUPTED로 보존한다. 폴링은1초 간격, 브라우저 이탈은 작업 취소를 뜻하지 않으며 돌아오면 job_id로 조회한다. 재시작 뒤 자동 모델 재실행은 없다. provider timeout 후 원격 연산 종료를 확인할 수 없으면 이전 호출이 미확정임을 기록하고 연속 자동 재시작을 막는다. 이전 성공 결과는 명시적인 이전 run 표시로 보존하되 설정 변경 후 새 결과처럼 보이지 않게 한다.

작업은 corpus/설정/hash가 같아도 fresh=true면 새 invocation/run 기록을 만들고 LLM 응답 cache를 사용하지 않는다. fresh=false는 성공 artifact 재생만 허용하며 없으면 명시 실행을 요구한다. overlap만 다른 파생 청크는 같은 parent 경계 artifact를 명시 재사용할 수 있고, 모델 호출0/새 호출을 구분한다. 종료 결과와 ledger는 원자적으로 저장한다. holdout 지표는 동결 상태에서 명시 실행 후에만 노출한다. 답변/인용/보류·Faithfulness/Correctness는 P008 확장이므로 P007에서 임시 점수를 만들지 않는다.

## 8. 검증·인계와 완료 경계

C1: 독립 문자열/유니코드/빈 단위/문단·소수점/긴 단위/최대길이·문서 경계·overlap·전체coverage·source map·section map·semantic 거리/동점, LLM JSON/ID/순서/마지막/길이/window/timeout을 검증한다. 모델 mock은 오류 fixture용이며 실제 모델 성공 근거로 쓰지 않는다.

C2: 두 span fact를 각각 다른 청크가 덮는 예, 중복 청크, 문서별 같은 offset,대체집합OR/내부AND 및 부분집합 섞기 거부, 공백만 overlap, 결과<K, 관련청크0, 답변불가, IDCG0의 수작업 기대값으로 지표/분모를 검증한다. 모델 정답/검색 qrels/policy-map이 검색·임베딩·LLM 청킹 입력에 유출되지 않는 read spy/요청 기록 검사를 포함한다.

C3: 고정 실험 결과·N/A/실패와 LLM3반복/호출 예산·대표 선택·cache 구분을 기록한다. 5개 방법의 실제 유효 출력/검색 연결이 필요하며 특정 방법의 우위는 불필요하다. 한 방법이 끝내 실행 불가능하면 완료로 가리지 않고 P007 차단/계약 재검토로 남긴다. P016 구조 기준을 충족해도 일부 방법의 경계가 같을 수 있으며 그것 자체는 실패가 아니다. 어떤 방법의 우위를 만들려고 원문을 수정하지 않는다.

C4: 원래 단계 파일·모델/lock·색인 보존 inventory, 새 단계 단독 임시 복사 CLI/API/모델 경로 확인, 기존 복사 코드 영향 회귀·가이드·manifest를 검증한다. 복사본은 같은 명시 소유 loopback 모델을 공유할 수 있지만 부모 Python import/경로 의존은 없어야 한다.

C5: 실제 브라우저로 PDF→추출→청크→검색 A/B를 정상/빈 결과/버전불일치/invalid config/모델 실패/중복 클릭/새로고침/재접속에서 확인한다. 키보드와390/1200px에서 읽기·설정·실행·비교·다운로드를 수행한다. mock 화면은 실제 코어 E2E를 대신하지 않는다. 저장 결과 재생은 모델 호출 없이, fresh LLM 버튼은 실제 제한 ledger로 확인한다.

증거는 `docs/verification/p007/`에 최초 실패/수정/최신 결과, 설정·출처·환경·사용량·브라우저 screenshot/trace·단독복사 결과·보존 inventory·최종 보고서를 보존한다. P013에는 선택 원문/청크·질문/검색 설정·run/index/code/model hashes와 모든 실패 한계를 인계한다. P013이 그 검색 결과를 승인 정답으로 삼지 않으며 실제 답변 run 생성은 별도 평가기 계약이다. P008은 이 UI에 실제 전달 문맥/답변/평가를 확장한다.

## 9. 확인한 API 문서와 적용 한계

2026-10-29 확인: Ollama [chat API](https://docs.ollama.com/api/chat)는 JSON schema format 및 완료/사용량 필드를 설명하고, [Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs)는 schema 지정 후 응답 검증 예를 제공한다. [embed API](https://docs.ollama.com/api/embed)의 truncate=false는 입력 한도 초과를 오류로 처리하는 계약이다. 이 문서 확인을 로컬 고정 버전/모델의 호환성 실험으로 대체하지 않는다. 실제 제한된 호환 probe/입력 상한 근거는 준비 검토에 남겼으며 전체 sweep/UI 검증은 dev가 수행한다.
