# P030 범용 모델 청킹 실행 계약 초안

2026-11-28 DRAFT. P020 최종 완료와 준비 검토 전에는 실행 인계가 아니다. [설계/기준 코드](P030-model-chunking-design.md)의 재사용 근거를 따른다. P013/P014 실험 보류·P029 미완료를 보존한다.

## 기능과 pipeline

공통 패키지에 fixed/recursive/structure/semantic/llm 다섯 방식을 연결한다. 임의 지원 PDF/TXT/MD snapshot에서 원문→unit→base 경계→overlap 청크→검색 index→선택 근거→답변 흐름을 사용한다. 기존 HR P007/P017·ledger/GT/실험 결과는 그대로 두고 순수 함수만 commit/path/hash provenance와 함께 선별한다. 별도 큰 번호 폴더를 만들지 않고 `2. Document Chunking/`의 고정 실험은 보존하며 공통 패키지 학습 자료를 추가한다.

`rag-lab chunk --snapshot DIR --config FILE --out DIR [--execute-chunking]`를 제공한다. 규칙 방식은 즉시 deterministic artifact 생성, 모델 방식은 기본 preview이며 명시 실행 시만 계산한다. 설정만 보고 결과를 반환하거나 규칙 fallback을 모델 성공으로 표시하지 않는다. `chunk-replay --run DIR`는 모델0으로 저장된 단위/경계를 확인한다. `chunk-derive --run DIR --config FILE --out DIR`는 허용된 threshold/길이/overlap 변경만 재사용하고 source/unit/model identity가 달라지면 새 실행을 요구한다.

새 RAG config v3는 schema_version/chunk_artifact/retrieval/embedding_config/llm_config를 가진다. chunk_artifact는 설정 파일 기준 경로이며 기존 v2 retrieval/embedding/LLM 의미를 계승한다. 기존 v1/v2의 inline 규칙 chunking은 호환 유지한다. build는 선택 snapshot과 chunk artifact의 source fingerprint를 일치시킨 뒤 index를 만든다. effective settings는 경로 대신 frozen chunk fingerprint/실제 method/config/model identity를 저장한다. 저장 build 및 P020 candidate/replay도 공통 source/interval 검증기로 모델 호출 없이 읽는다. 기존 load_build/candidates.load의 make_chunks 재실행을 모델 호출로 확장하지 않는다.

## 단위와 길이

canonical NFC/LF Unicode codepoint `[start,end)`를 사용한다. 단위는 각 문서에서 문단→문장 끝/제목 경계와 deterministic 긴 단위 분할을 조합하고 원문 전체를 순서대로 덮는다. unit IDs는 source/document/interval/단위화 version에 묶인다. 공백·개행을 조용히 삭제하지 않는다. heading_path/page는 원문 mapping에서 유도하고 모델이 만든 텍스트를 추가하지 않는다. unit 강제 분할·window 끝·길이 제한 경계와 모델이 고른 경계를 따로 기록한다.

chunk config v1 공통은 schema_version/method/size_chars/overlap_chars, size100..4000, overlap0..min(400,size-1). 규칙3종은 기존 P026 의미와 동일하다. semantic/llm은 최종 청크 최대 size를 지키기 위해 base_max=size-overlap, unit 최대=min(400,base_max), minimum_chars1..base_max를 사용한다. post-partition left extension은 이전 base start를 넘지 않는다. fixed sliding overlap과 model-based extension 차이를 표시한다.

semantic 추가 필드는 embedding_config/distance_threshold(유한0..2)/minimum_chars. llm 추가 필드는 llm_config/window_max_chars(100..4000,기본1200)/window_max_units(1..40,기본20)/max_windows(1..128,기본64)/max_prompt_bytes(1024..65536,기본16384)/total_timeout_seconds(1..3600,기본1800). 적용되지 않는 필드는 거부한다. 모든 문서의 단위 수 최대5000, 모든 output chunks 최대10000. 한도가 부족하면 첫 모델 호출 전에 전체 입력을 거부하고 일부 문서만 성공한 것으로 나타내지 않는다.

## Semantic 모델과 파생

P010 E5/BGE profile과 실제 encode worker를 재사용한다. 경계용 unit는 document prefix/preprocessing/길이 검사로 인코딩하고 finite/nonzero/차원·수/순서·정규화를 검증한다. unit 개수는 profile max_chunks와 본 계약 상한 중 낮은 값 이내다. 기본값을 우회해 대량 실행하지 않는다. 실제 SDK tiny 모델 시험과 주입 vector 산술 시험은 별도 증거다.

semantic 알고리즘은 인접 unit의 `1-cosine` 거리이다. 현재 base 길이가 minimum_chars 이상이며 거리>=threshold이거나 다음 unit를 포함하면 base_max를 넘을 때 경계를 고른다. 거리와 각 결정 이유를 기록한다. 문서 간 거리를 계산하지 않는다. 동일 unit/model/preprocessing/SDK일 때만 저장 float32 unit vectors를 재사용한다. vectors byte hash와 순서 hash를 포함하고 dtype 정밀도로 인한 재생 결과가 달라지지 않도록 **저장 정밀도로 고정한 벡터**로 최초 경계를 계산한다. 파생 작업은 저장된 unit map/단위화 정책을 그대로 사용한다. 새 base_max가 저장 unit 하나보다 작으면 reuse 불가이며 새 단위화가 필요하다. source text 또는 모델 변경도 reuse 불가다.

오버랩 파생은 unit/base 경계를 유지하고 emitted interval만 바꾼다. 모든 파생 청크가 새 size_chars 안에 들어오는지 먼저 검사하고 초과하면 derived_size_exceeded로 거부한다. 모델을 다시 불러 분할하거나 조용히 overlap을 줄이지 않는다. 사용자는 size를 늘리거나 명시 새 경계 생성을 선택한다. 파생 artifact는 parent의 unitization/base policy와 새 emission policy를 각각 기록한다. LLM derive는 source/model/prompt/window/end IDs를 바꾸지 않는 overlap 및 충분한 emission size 변경만 허용한다. Semantic derive는 저장 unit가 들어가는 범위의 base_max/minimum/threshold/overlap 변경까지 가능하고 저장 정밀도 vector로 경계를 다시 계산한다. 원 경계와 새 경계 모델 실행을 혼동하지 않는다. 새로운 청크 text/ID에는 새 검색 index가 필요하며 unit vector를 최종 chunk embedding인 것처럼 쓰지 않는다.

## LLM 역할·요청·검증

LLM config v2는 기존 profiles와 generation/evaluation에 chunking 역할을 명시적으로 추가한다. v1 generation/evaluation은 기존 동작 유지, v1에서 chunking 호출은 명확한 미설정 오류. profile·provider validation/identity/previews·normalized statuses는 P025를 계승한다. 같은 프로필을 세 역할에 매핑할 수 있으나 evaluation은 이 카드에서 호출하지 않는다. UI에서 generation 모델 선택이 chunking 모델을 조용히 바꾸지 않는다.

LLM은 query/GT/qrels 없이 unit ID와 exact source text, 경계 지시를 받는다. 원문 안 명령은 데이터로 취급하며 출력은 end_unit_ids만인 JSON이다. Ollama/OpenAI Chat/Anthropic 세 adapter의 JSON mode·추가 system 지시를 반영한 actual_messages와 request hash를 사전 기록한다. 알 수 없는 ID, 중복/역순/최종 ID 누락, base_max 초과, 불완전/잘린 응답·거부·tool use·원문 재작성은 실패다. 허용된 경계로 Python이 canonical slice를 만든다.

각 window는 동일 문서의 연속 unit, window_max_chars와 units 이내다. 하나의 unit가 window에 안 들어가면 명시 실패한다. 모든 window payload/최대 prompt bytes/총 window 수/필요 호출 수를 실행 전에 검증한다. bytes/문자 상한은 토큰 한도와 다르다. 정확 tokenizer/template token 측정이 없으면 token count는 null/미측정이고 모델 고유 context window 보장을 표시하지 않는다. provider 길이 초과나 finish reason=length는 실패이며 원문 축약/재청킹/다른 모델 자동 전환은 없다. model profile의 timeout/max_output_tokens는 별도로 적용한다.

retry0, 실패 시 남은 window 중단. total deadline을 첫 호출 전 시작하고 각 요청 timeout은 남은 deadline 이하로 제한한다. 기존 HTTP adapter가 deadline을 넘기는 모델 내부 실행을 직접 종료했다고 주장하지 않는다. timeout의 outcome_unknown을 유지한다. 명시 재실행은 새 invocation이며 이전 시도·소비를 지우지 않는다. 실행 요청 window 수, 실제 dispatch·성공·실패·미확정 수, 입력/출력 usage 또는 null, 소요 시간·비용 미측정과 실패 위치를 기록한다. 별도 작업 디렉터리의 durable invocation 기록을 실행 전 만들고 상태를 갱신하며, 저장 실패 후 자동 재요청하지 않는다. P007/P013 grant/ledger는 사용하지 않는다.

## Artifact·실패·호환

성공 artifact에는 source snapshot, units, base boundaries/선택 end IDs 또는 semantic distances, emitted chunks와 coverage/page/heading map, model/config/SDK/prompt identities, 실행 통계·파생 parent fingerprint를 봉인한다. semantic vectors는 numeric binary만이며 pickle 없음. source/interval/text/hash 및 partition coverage·최대길이·overlap 의미를 로드 시 재검증한다. LLM raw 응답은 진단 입력으로 분리하며 검증되지 않은 문자열을 청크나 UI HTML로 실행하지 않는다.

실패/중단은 invocation 진단으로 보존하고 ready chunk artifact/index/UI 선택 목록에 올리지 않는다. 원문/설정 preview는 호출0, chunk-replay/derive는 model0. 조회·검색·새로고침으로 경계 추론을 재개하지 않는다. source/query/chunk/index identity를 섞지 않는다. UI는 기존 serial job·중복 request·재시작 interrupted를 계승하며 별도 `--allow-chunking-execution` 기본false, chunk config/LLM/embedding profile은 서버 등록 opaque ID로 선택한다. API 키는 이미 선택된 provider 실제 호출 시만 읽는다.

## 비교·가이드·검증

같은 source와 질문·검색 설정에서 다섯 방식의 경계/원문·chunk 수/길이/중복/강제분할·모델과 색인 비용·검색 후보/전달 근거를 비교한다. 모델 경계 생성과 검색을 별도 작업으로 수행해 저장 결과를 선택하고, compare가 경계를 암묵적으로 새로 생성하지 않는다. P020 source fact/span 지표로 청킹 간 근거 회수를 비교하고 chunk qrels는 각 chunk fingerprint의 별도 입력이 있을 때만 사용한다. GT/qrels 없는 일반 문서 품질은 N/A, Faithfulness/Correctness evaluator는 미연결이다.

준비된 독립 기대값은 설계 문서의3unit vector·임계값·길이/LLM end IDs/overlap·fact 예시를 따른다. 추가로 다문서·빈문서/공백·제목·Unicode·window 경계·단위 초과/전체 사전거부·wrong model/source·vector bytes 변경·불완전 JSON·실패 두 번째 window·deadline/unknown·쓰기 실패/재시작·model0 재생/색인 조회를 검증한다. 가짜 세 provider를 통한 경계 선택과 실제 SDK tiny unit encode를 구분하고 실제 모델 품질이라고 부르지 않는다.

설치물·CLI·학습 UI와 가이드 `docs/learning/rag-package/model-chunking.md`, 다섯 설정 예시/실습자료를 제공한다. source 없는 새 venv/일반 문서로 경계 생성→저장 선택→검색→P020리랭커/답변 preview 연결을 검증한다. 허용 브라우저에서 원문·경계·예산/비용·실패와 좁은 화면/키보드 확인, 파일 선택창의 기존 정책 거부는 우회하지 않는다. 필수 회귀/guard/선별 출처·hash 보존/소유 worker 종료/커밋 증거/정상 personal-dev 전달이 필요하다.

이 초안의 개발 검증은 실제 LLM/API/Drive/OAuth/키 및 사전학습 모델 호출0이다. 유료 API/로컬 모델을 사용할 수 있는 실코드는 구현하지만 실제 성능·리소스 비교는 별도 live 계약으로 검증한다. P020 완료 SHA와 실제 source/fact/UI 인터페이스, 위 상한 및 fixture를 준비 검토한 뒤 카드와 함께 READY로 확정한다.
