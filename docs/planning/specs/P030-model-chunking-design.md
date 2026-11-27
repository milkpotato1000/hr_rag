# P030 모델 기반 청킹 연결 설계

2026-11-28 DRAFT. P020 구현 중 plan이 다음 남은 goal 범위를 준비한다. 실행/모델 호출 권한이 아니며 평가기 실험 보류를 해제하지 않는다.

## 기존 코드에서 확인한 차이

P010 완료3d99353 기반의 `rag_package/chunks.py`는 fixed/recursive/structure만 지원한다. `retrieval.build`와 `load_build`가 make_chunks를 호출해 생성 및 무결성을 확인한다. 여기에 모델 호출을 넣으면 색인 조회마다 재추론하거나 경계가 달라질 수 있으므로 그대로 확장하면 안 된다.

`2. Document Chunking/scripts/chunk_core.py`는 boundary_units/unit_windows/semantic/llm_partition/parse_boundaries/extend를 갖고 있다. semantic은 인접 원문 단위의 코사인 거리와 최소/최대 길이로 경계를 고른다. LLM은 end_unit_ids만 고르고 Python이 원문을 자른다. 이 순수 알고리즘/검증 원칙은 재사용 가능하다. 하지만 build는 고정 EXP/boundary-map.json/source/runtime와 P007 Provider에 묶여 있으며 Qwen3:4b 모델명·frozen template·8192 예산·최대35window·2회 시도를 전제로 한다. 이를 범용 provider로 단순 alias해 현재 예산이나 검증을 계승했다고 주장하지 않는다.

P025 `llm.config.validate_config` 및 `llm.core.preview`는 generation/evaluation 두 역할만 허용한다. LLM 청킹을 evaluation 이름으로 우회하면 보류된 평가기와 실행 의미가 섞인다. versioned 설정 또는 명시적인 추가 chunking 역할을 마련하고 기존 두 역할 설정은 호환 유지한다. 역할별 모델 선택을 지원하되 여러 모델 동시 상주를 기본으로 하지 않는다.

## 경계와 원문을 분리하는 구조

먼저 동일 canonical snapshot을 단위로 나눈다. 문단/문장/제목 후보 경계와 긴 단위의 강제 분할을 deterministic하게 기록한다. 각 단위는 document ID·start/end·text hash·boundary reason을 가진다. 문서를 넘어 묶지 않고 source의 NFC/LF Unicode codepoint interval을 보존한다. 강제 분할/독립 window 끝은 의미 모델이 고른 경계처럼 표시하지 않는다. 제목 경로는 metadata이며 모델이 만든 제목/요약을 원문인 것처럼 끼워 넣지 않는다.

새 chunk artifact는 source fingerprint, 알고리즘/설정, unit map, 선택 base boundaries, overlap 확장 구간, 정확 원문 청크·page/heading mapping, 모델/요청/출력 hashes, 실행 종류·시도/비용·실패를 보존한다. 성공 partition은 모든 원문을 빠짐없이 순서대로 덮어야 하고 whitespace-only 제외는 별도 coverage에 남긴다. canonical source와 stored intervals/text를 대조해 무결성을 검증한다. 모델 출력 본문을 청크 본문으로 저장하지 않는다.

build는 frozen chunk artifact를 받아 새 검색 index를 만든다. load/replay는 source/설정/unit/interval/coverage/hash를 검증하고 모델을 호출하지 않는다. 규칙3종의 기존 schema v1/v2와 artifact는 기존 동작을 유지한다. 새 schema/CLI에서 model chunk 결과를 명시적으로 연결한다. 같은 경계에서 overlap만 바꾼 파생 결과와 모델을 다시 실행한 독립 실험을 구분한다. 파생 provenance와 실제 호출0을 기록하고 독립 반복으로 세지 않는다.

## 의미 기반

P010의 공개 HF embedding profile을 선택하고 동일 원문 단위를 document 입력으로 인코딩한다. 검색용 embedding과 경계용 embedding을 다른 설정으로 둘 수 있되 identity/작업 수/비용을 분리한다. 저장 unit vector를 threshold/길이/overlap 비교에 재사용할 때 source/unit/model/tokenizer/preprocessing/SDK/hash가 같아야 한다. 모델/단위 변경은 재계산 대상이다. embedding 없이 임의 경계를 semantic 성공으로 제공하지 않는다.

기본 방법은 인접 unit 거리 `1-cosine`과 minimum/base maximum 조건이다. global topic clustering이나 학습된 segmentation으로 설명하지 않는다. 분할 이유는 semantic/maximum/forced-unit/document-end로 남긴다. max 길이가 단위보다 작을 때 단위화를 재정의해 identity를 바꾸거나 명시 실패하는 정책을 READY에서 고정한다. 의미 임계값과 overlap은 별도 축이며 실제 품질 우수성을 미리 가정하지 않는다.

## LLM 기반

질문/GT/qrels와 무관하게 원문 unit ID와 text, 경계 선택 규칙만 LLM에 준다. 출력은 `{"end_unit_ids":[...]}`이며 허용 ID/순서/중복/최종 ID/최대 길이/완전 coverage를 검증한다. 답변 요약이나 원문 재작성은 허용하지 않는다. 모델·prompt·provider actual_messages hash, 정확 config/runtime identity를 기록한다.

원문을 유한 window로 나누고 모든 payload의 크기·unit 수·예상 호출 수를 실행 전에 검사한다. 작은 window마다 독립 결정하므로 window 사이 주제 연결을 못 보는 한계를 표시한다. provider별 tokenizer/template 검증이 없는 문자 수를 context window token 보장으로 쓰지 않는다. 지원 모델의 정확 token preflight 또는 명확한 미검증/실행 불가 정책을 READY에 정한다. API output budget·finish reason과 invalid/length-truncated response를 구분한다.

기본 retry0, timeout/unknown outcome 이후 자동 재요청0. 부분 성공 경계는 진단 이력으로 남기되 정상 전체 chunk artifact로 노출하지 않는다. 모델 선택/문서 변경/재실행은 새 invocation과 누적 ledger를 사용하고 화면 새로고침이 예산을 초기화하지 않는다. 정확 unit/window/시간/요청·응답 크기 상한과 실험별 총량은 준비 검토에서 고정한다. P007/P013 grant는 재사용하지 않는다.

## 비교와 UI

원문 snapshot/질문/retriever·embedding·reranker/K/문자 예산을 고정하고 청킹 축만 바꾼다. 청크 수·길이분포·오버랩 중복·강제 경계·경계 모델비용·색인비용·검색/전달 근거를 구분한다. 조회/임계값 재생과 새 모델 추론을 같은 시간 측정으로 섞지 않는다.

청킹을 바꾸면 chunk ID와 관련 청크 분모가 달라지므로 primary 비교는 source 기반 필수 fact/span 회수와 전체 필수 근거 충족을 사용한다. P020의 union·AND/OR 정책과 실제 코드 API를 재사용한다. chunk qrels는 각 chunk fingerprint에 맞는 별도 정답이 있을 때만 보조 지표로 보고한다. old qrels를 새 chunk ID에 임의 변환하지 않는다. GT/fact가 없으면 정량 품질은 N/A이며 원문/경계/청크·비용 비교는 가능하다.

UI는 방법5종/모델 profile/크기·오버랩·임계값·실행 허용을 분리한다. 설정만으로 추론하지 않고 boundary preview→실행→저장 결과 선택→검색 비교가 실제 코어로 이어진다. 선택된 원문/모델/경계 hash와 실행 종류를 보여주고 실패/미실행을 규칙 fallback 성공으로 바꾸지 않는다. 현 P007 화면을 그대로 띄우는 것이 아니라 generic 문서/설치 패키지에 연결한다.

## READY 전 확인

1. P020 최종 후보/fact/registry/CLI 공개 경계를 대조하고 구체적인 chunk artifact/schema/entrypoint를 확정한다.
2. P007 선별 코드의 commit/path/hash 및 기존 경계·실험/GT/ledger 보존 범위를 기록한다.
3. 모델별 token preflight와 LLM role/config version, total budget/부분실패/파생·독립 실행 의미를 확정한다.
4. 손계산 unit vectors/임계값/길이·동점·오버랩·다문서/AND·OR 정답, 실제 tiny SDK와 가짜 세 provider·replay0모델·색인조회0모델 시험을 준비한다.
5. source-free wheel/실습/CLI·허용 UI 관찰과 회귀·증거를 정한다. 사전학습 품질·실제 API/로컬 모델 실험은 별도 명시 범위가 필요하다.

## 저장·재실행 경계 구체화

P030의 핵심 분리는 `snapshot → chunk artifact → index → retrieval → optional rerank → answer`다. 기존 build의 규칙 청킹 경로는 호환으로 남기되 새로운 model-based chunk artifact를 전달하는 진입점을 마련한다. source에서 다시 모델 경계를 추정하여 저장 결과와 비교하지 않는다. load 검증은 저장된 입력·출력·unit/interval을 결정적으로 재생하는 것으로 충분하며 모델을 다시 호출하는 검증은 금지한다.

| 작업 | 경계용 모델 | 검색용 embedding | LLM generation |
| --- | --- | --- | --- |
| 설정 preview / 원문·저장 경계 보기 | 0 | 0 | 0 |
| 규칙 청킹 새 artifact | 0 | 0 | 0 |
| 의미 청킹의 새 unit vector 생성 | 선택 HF 모델로 단위 인코딩 | 0 | 0 |
| 동일 unit vector에서 threshold/길이 변경 | 0, 저장 vector 재사용 | 0 | 0 |
| LLM 청킹 새 경계 | chunking 역할, window별 호출 | 0 | 0 |
| 저장 base 경계의 overlap 파생 | 0 | 0 | 0 |
| frozen 청크로 Dense/Hybrid 새 색인 | 0 | 선택 HF 모델로 청크 인코딩 | 0 |
| 저장 색인 조회/문서 vector 재사용 | 0 | 문서0; 질문 검색은 query embedding 필요 | 0 |
| 선택 근거로 답변 | 0 | 0, 저장 선택 재사용 | generation 역할 최대1회 |

실행 flag도 단계별이다. chunking 모델 계산 허용을 retrieval 계산/generation 실행 허용으로 대체하지 않는다. UI에서 한 번의 명시적 pipeline 실행을 제공할 경우 선택된 각 단계와 예상 작업 수를 먼저 보여주고 내부 stage별 허용을 기록한다. 설정 변경·화면 이동·조회는 실행 동작이 아니다.

의미 거리와 최소/최대 base 길이가 바뀌어도 unit map·모델·전처리가 같다면 unit vector 캐시를 재사용할 수 있다. 반면 청크 경계/오버랩이 달라지면 검색에 쓰는 청크 text와 ID가 달라지므로 검색 index는 새로 만들어야 한다. unit embedding과 최종 chunk embedding을 같은 캐시 키로 취급하지 않는다. 임베딩 모델을 선택할 때 이 두 용도를 UI와 로그에 별도로 표시한다.

## 원문과 경계의 독립 기대값 초안

단일 문서의 단위 구간을 [0,4),[4,8),[8,12)로 고정하고 vector를 (1,0),(1,0),(0,1)로 둔다. 인접 거리는0,1이다. threshold=.5,minimum4,base maximum12면 경계는[0,8),[8,12). threshold1.5면[0,12), base maximum8이면 거리 조건과 무관하게[0,8),[8,12)다. threshold를 바꿔도 unit vector 생성 호출은 늘지 않아야 한다.

LLM 응답 end_unit_ids=[u1,u2]는 같은 [0,8),[8,12)를 선택한다. unknown ID, [u2,u1] 역순, [u1,u1,u2] 중복, 최종 u2 누락, 허용 길이 초과, JSON 외 본문, finish reason=length는 실패다. chunk text는 항상 canonical slice이고 LLM이 바꾼 표현이 저장되면 오류다. 첫 window 성공/둘째 실패 시 전체 ready chunk artifact는 없어야 하며 성공 window 비용과 실패/unknown 호출 기록은 남는다.

base spans[0,8),[8,12)에 overlap2를 적용하면 emitted spans는[0,8),[6,12)다. base coverage는12자, 저장 text 합은14자, 중복2자다. base maximum을 size_chars와 같은 의미로 노출하지 않고 overlap을 더한 최종 최대 길이를 검사한다. 기존 fixed의 sliding-window 방식과 model-based post-partition overlap 방식 차이는 알고리즘 version/가이드에 명시한다. source fact[7,9)는 첫 청크만으로 충족되지 않지만 overlap이 있는 둘째 청크가 충족한다. fact를 담은 청크 수가2가 되더라도 같은 fact 성공은1회다.

위 숫자는 원리 검증용 작은 fixture다. 사용자 최소 크기와 분리된 순수 함수 시험으로 적용하며 production 제한을 테스트 편의로 완화하지 않는다. UTF-16 surrogate/한글 결합문자/NFC·LF 입력과 다른 문서의 같은 offset을 추가해 원문 mapping을 검증한다.

## Provider 역할과 입력 길이의 구현 선택 초안

현재 LLM config v1을 그대로 지원하며 v2에서 `roles.chunking`을 추가하는 방향을 우선 검토한다. generation/evaluation 프로필을 자동 덮어쓰지 않고 chunking에 명시한 프로필을 사용한다. API는 이미 구현된 provider와 동일한 인증/요청 경계를 사용하며 LLM chunking 때문에 공개 embedding이나 reranker가 유료 API로 바뀌지 않는다. 사용자가 같은 모델을 여러 역할에 지정할 수는 있다.

LLM window 한도는 raw 원문 글자·unit 수와 실제 prompt/JSON bytes를 별도로 제한한다. 이것만으로 임의 provider의 token window를 보장하지 않는다. 알려진 로컬 tokenizer/template의 검증 가능한 token count는 근거와 함께 기록하고, API의 정확 count를 모르면 미측정으로 표시한다. provider가 길이 초과/응답 잘림을 반환하면 전체 경계 실행은 실패로 남기며 조용한 내용 축약이나 자동 다른 모델 전환을 하지 않는다. 각 실제 모델 실행의 context/출력/전체요청 예산은 별도 live 계약에서 확정한다. 이 초안은 provider API에 없는 token count를 있다고 가정하지 않는다.

## 읽은 기준 소스

기준 P010 완료 `3d99353b5aef3b683b24d0f7fa06b8a757dc1f83`. 아래 파일은 읽기만 했으며 P007/P017 코드나 ledger를 변경하지 않았다.

- `2. Document Chunking/scripts/chunk_core.py`: SHA256 `adc59a6662a8e155d9e41773afbed1dcc4e5d62626072724e94ee39c6d54a018`.
- `2. Document Chunking/scripts/chunk_settings.py`: SHA256 `58d3deaad3fc256a0982ba768702346ba1440e6187a529334267ade3b0667e4d`.
- `rag_package/chunks.py`: SHA256 `8aa924d3ab7693027d96302edefd7dedbdff7e16de8caf2229afe64083f6db52`.
- `rag_package/llm/config.py`: SHA256 `a67983910667cfbcf76e4adbbe1aa777e62395039e9775fd52dbc9db59a7817a`.
- `rag_package/llm/core.py`: SHA256 `d18fc650f4ab72e1db351615e7e05056675f57544243bff5c17b045e3998e8e7`.

## 파생 크기 충돌 검토 — 2026-11-28

동일 base 경계에 overlap을 추가하면 최종 size를 넘을 수 있다. 실행 계약 초안은 이를 derived_size_exceeded로 거부하고 size 확대 또는 명시 새 경계 생성으로 구분한다. 저장된 단위화 정책과 파생 emission 정책을 분리하므로 overlap만 바꿨다는 이유로 모델을 재호출하지 않는다. semantic 재생은 저장 unit가 새 base_max에 들어갈 때만 가능하며, LLM 경계/모델/prompt/window 변경은 파생으로 위장하지 않는다.

단위 token 초과의 복구를 최종 청크 크기 변경과 분리하기 위해 모델 방식에 unit_max_chars를 둔다. 기본은min(400,size-overlap), 고급 설정에서 더 작게 선택 가능하며 변경 시 unit identity와 vector 캐시는 새로 만든다. 예를 들어 최종800자 청크를 유지하면서 경계 판단 단위만100자로 줄일 수 있다. 실제 token 한도 검사는 여전히 모델 tokenizer가 수행한다.
