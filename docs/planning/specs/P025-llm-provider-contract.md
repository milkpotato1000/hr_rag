# P025 공통 LLM 연결 계약 v1

## 목적과 코드 경계

2026-11-27. 공개 모델 기본/상용 LLM API 선택을 실제 호출 가능한 독립 모듈로 만든다. 루트 `rag_package/llm/`에 설정·요청 변환·응답 정규화·transport·CLI를 둔다. `tests/rag_package/`와 `examples/llm/`, `docs/learning/rag-package/providers.md`를 추가한다. Python 3.10+ 표준 라이브러리로 구현하며 신규 설치/네트워크 의존성을 추가하지 않는다. 모듈 내부 함수/클래스 분리는 dev 판단이다.

기존 `1. Naive RAG/variants/langchain/scripts/generation.py:107`의 Generator는 특정 모델·digest·Ollama 버전·schema에 고정돼 있고 `rag.py:144`의 ask는 해당 lock 구조를 사용한다. `evaluation/project_b/evaluator.py:101`의 payload 역시 Qwen8B와 역할별 schema에 고정돼 있다. 이들 계약을 바꾸지 않고 새 경계의 CLI/라이브러리부터 만든다. 실제 RAG 연결은 다음 카드에서 이 모듈을 사용한다. 모듈만 완성됐다고 RAG UI API 선택 완료라고 하지 않는다.

## 최초 지원 범위와 근거

| provider 값 | mode | wire endpoint/처리 |
| --- | --- | --- |
| ollama | local | numeric loopback HTTP base + `/api/chat`, `stream:false`, `think:false`, options와 keep_alive:0 |
| openai_chat | api | HTTPS base(기본 https://api.openai.com/v1) + `/chat/completions`, Bearer key, nonstream 1개 choice |
| anthropic_messages | api | HTTPS base(기본 https://api.anthropic.com/v1) + `/messages`, Bearer key, `anthropic-version:2026-10-21`, nonstream |

공식 wire 근거(2026-11-27 확인): [Ollama chat](https://docs.ollama.com/api/chat), [OpenAI Chat Completions create](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [Claude Messages create](https://platform.claude.com/docs/en/api/http/messages/create). Chat Completions를 호환 protocol의 첫 대상으로 쓰며 모든 공급자가 같다고 주장하지 않는다. Responses API, Gemini 고유 protocol, streaming, tool calls, multimodal은 별도 확장이다. Anthropic의 현재 예시는 Bearer 인증/위 버전이므로 옛 x-api-key/2023 버전을 자동 가정하지 않는다.

모델 이름은 사용자가 지정한다. 상용 모델 이름/가격을 추측해 기본값으로 넣지 않는다. Ollama 예시는 기존 Qwen4B/8B lock의 정확 digest와 알려진 변형 identity를 인용하되 해당 기기에서 사용 가능하다는 검증 완료로 표시하지 않는다.

## 설정과 요청

- `schema_version:1`, `profiles`는 이름→profile, `roles`는 generation/evaluation→profile 이름이다. 둘이 같은 profile을 써도 되고 다르게 골라도 된다. extraction/faithfulness/correctness 등은 상위 평가 역할 안의 요청 목적이며 이 모듈은 판정 프롬프트/채점법을 바꾸지 않는다.
- profile 필수: mode, provider, model, base_url, max_output_tokens, timeout_seconds, response_mode(text/json_object), api_key_env(api만), identity. 선택: temperature(null이면 전송하지 않음), Ollama num_ctx/seed. 명시 schema 밖의 필드, bool-as-int, nonfinite, 빈 모델, 공백뿐 값, 없는 role 참조를 거부한다. 크기 한도: max_output_tokens 1..32768, timeout 1..600초, num_ctx 512..131072; 입력 파일 2MiB, HTTP 응답 4MiB 상한. 이는 runtime 보호 범위이며 모델의 실제 context window를 보장하는 값이 아니다.
- local identity에는 `expected_digest` 전체 SHA256, 원본 HF ID/변환 identity 설명을 포함한다. API identity에는 요청 model과 revision 고정 여부를 표시한다. 원본 revision을 모르면 null/unknown으로 기록하고 가짜 HF revision을 만들지 않는다. 원본 HF/변환/양자화 metadata는 설명용이며 서버 digest 대조를 대신하지 않는다.
- API key는 이름 참조만 설정에 넣는다. `validate`와 `preview`에서는 키 값·존재 여부를 읽지 않는다. invoke 직전에 해당 env만 읽고 없으면 전송0으로 명확히 실패한다. URL userinfo/query/fragment, 제어 문자, path traversal을 거부한다. local은 숫자 loopback만, API는 HTTPS만 허용한다. 인증 header에 제어 문자가 있으면 거부한다.
- `messages` 파일은 role(system/user/assistant)과 문자열 content만 지원한다. system은 시작에 최대1개, 최소1 user, user/assistant 교대로 정렬된 입력, 마지막 user로 제한한다. 미지원 role/content/tool을 자동 변환하거나 누락하지 않고 거부한다. Anthropic은 선두 system을 top-level system으로 옮기고 나머지 순서를 보존한다.
- API는 temperature를 기본 생략한다. openai_chat은 max_completion_tokens, Anthropic은 max_tokens, Ollama는 num_predict로 출력 예산을 변환한다. seed/num_ctx/think/keep_alive는 Ollama에만 전송한다. 미지원 옵션은 다른 provider로 흘러가지 않는다.
- json_object 모드는 공통 JSON 지시를 별도 추가하고 변경된 실제 messages hash를 기록한다. Ollama `format:json`, OpenAI `response_format:{type:json_object}`, Anthropic은 JSON 지시와 로컬 parsing 검증을 사용한다. Anthropic에 native schema 보장을 주장하지 않는다. 임의 JSON Schema 지원은 이번 범위가 아니며 상위 RAG/평가기가 자신의 출력 schema를 검증해야 한다.

## 실행과 transport

`python3 -m rag_package.llm validate --config ...`, `preview --config ... --role ... --messages ...`, `invoke --config ... --role ... --messages ... --output <새 파일>`을 제공한다. validate/preview/help/import는 파일 검증만 하고 socket·키 조회·서버·모델에 접근하지 않는다. preview는 설정과 wire body를 보여줄 수 있으나 키 헤더는 표시하지 않는다. 공유 전 private 문서 포함 여부를 사용자에게 안내한다.

invoke는 실제 구현된 HTTP 경로다. 이번 P025 검증에서는 injected transport/로컬 가짜 HTTP 서버로만 실행하고 실제 Ollama/API 호출은 0회다. 런타임 서버 시작·다운로드·프로세스 종료 기능을 만들지 않는다. P013 중지/원본 ledger를 건드리지 않는다. 실제 실행 성공 여부는 별도 제한 있는 실행 검증 후 기록한다.

- 기본 transport는 timeout·response size 한도를 적용한다. 자동 redirect·retry·provider fallback 없음. proxy는 기본 사용하지 않고 이를 안내한다. SSL 검증을 끄지 않는다. 오류 응답 원문/headers/request body/key/env를 예외나 일반 로그로 내보내지 않는다.
- Ollama invoke는 `/api/tags`에서 선택 모델 digest를 대조한 후 한 번 chat, 이후 다시 digest 확인한다. preflight 불일치/없음이면 chat0. postflight 불일치면 결과를 성공으로 취급하지 않는다. 모델 이름이 같아도 digest가 바뀐 사례를 시험한다. 키 조회와 실제 HTTP는 invoke 경계에만 있다.
- 선택 API의 request body와 제한은 명시하며 한 번의 invoke는 생성 요청 최대1회다. timeout 이후 자동 재시도하지 않고 전달/과금 여부 불명 가능성을 기록한다. fixture 재생은 actual model run으로 표시하지 않는다.
- transport는 주입 가능하되 실제 HTTP 경로도 구현한다. 테스트 전용 canned output을 프로덕션 기본으로 연결하지 않는다. 외부 서비스 요청을 테스트에 요구하지 않는다.

## 정규화된 결과

schema_version, status, content, parsed_json, provider, requested_model, response_model, role, identity_verification, finish_reason, usage, elapsed_ms, request_fingerprint, error를 반환한다. usage는 입력/출력 토큰을 가능한 경우 변환하고 미제공은 null이다. 단위가 다른 duration은 명시적으로 변환한다. 비용은 이번 모듈에서 계산하지 않고 null/unmeasured다. raw provider body나 hidden thinking은 결과에 저장하지 않는다.

status는 complete / truncated / refused / unsupported_response / invalid_response / error를 구분한다. complete 외 결과를 성공 답변으로 표시하지 않는다. json_object에서는 완결된 정상 응답만 strict JSON parse(중복 키/NaN/Infinity 거부)하고 최상위 object 여부를 확인한다. fenced JSON을 자동 복구하거나 누락 내용을 생성하지 않는다.

정상 finish는 Ollama stop, OpenAI stop, Anthropic end_turn/stop_sequence. length/max_tokens는 truncated, refusal/content_filter는 refused, tool_calls/tool_use 또는 알 수 없는 content block/finish는 unsupported_response. envelope 누락·모델명 누락·choices 여러 개·비문자열/빈 content·Ollama done:false는 invalid_response. 응답 model은 기록하되 API alias의 요청값과 같아야 한다고 가정하지 않는다. Ollama는 선택 model과 일치해야 한다. provider가 반환한 thinking 블록은 저장하지 않으며 text와 섞어 답변으로 취급하지 않는다.

HTTP 401/403/429/5xx, 연결 오류, timeout은 각각 기계 판독 가능한 error code. dispatch_attempted 및 outcome_unknown을 구분하고 exception 문자열/원문 응답을 반환하지 않는다. config/message 오류 역시 입력 내용·비밀값을 반복하지 않는 경로/필드 기반 오류를 사용한다. CLI exit0은 validate/preview 성공 또는 invoke complete일 때만, 나머지는 nonzero와 JSON 오류다. 결과 파일은 새 경로에 원자적으로 기록하고 기존 파일을 덮어쓰지 않는다. 선택 파일에 정상 content가 저장되므로 비공개 문서는 public artifact로 자동 기록하지 않는다.

## 독립 검증 행렬

1. 같은 요청을 세 provider로 routing해 method/URL/인증 종류/출력 예산/system 분리/role 선택/불필요 옵션 없음 대조. 같은 canonical 의미 입력 보존.
2. text/JSON 정상, 실제 각 envelope의 usage 유무, unknown 사용량 null, API alias model, local digest before/after mismatch.
3. 잘못된 config/URL·role·수치·키 누락·messages 및 example_only 문서 예시를 거부. validate/preview는 key resolver와 socket 호출을 실패하도록 주입해도 통과.
4. 길이 종료·refusal·tool request·unknown block·잘못된/중복/nonfinite JSON·빈 응답·role/model/done 오류를 성공과 구분.
5. 401/403/429/5xx·timeout·oversize·redirect·연결 실패, 재시도0 및 key가 든 synthetic 오류/body/URL에서도 출력·로그 누출0. fake HTTP 서버로 기본 transport의 redirect·size·JSON 경계를 검증한다(로컬 모델 서버 아님).
6. API env 값은 생성한 fake 문자열만 사용. 실제 사용자 키 읽지 않음. 외부 네트워크를 차단한 테스트 경로에서 전체 실행. 기존 Naive/Chunking/evaluation 코드/lock/artifact hash 불변, P013 BLOCKED/로그 불변 확인.
7. examples/llm의 새 설정은 실제 schema를 통과하고 기존 P024 example_only 예시는 설명용으로 보존·링크한다. README/학습 상태표를 adapter 구현·offline 검증 완료 / live 및 RAG 연결 미검증으로 갱신.

증거는 docs/verification/p025/에 명령·테스트·지원 상태·제한·보존 hashes를 기록한다. 통과한 계약 시험을 한국어 모델 품질·메모리 PASS로 바꾸어 보고하지 않는다.
