# 공통 LLM adapter 사용 안내

P025는 **독립 LLM 호출 모듈과 CLI**를 구현했습니다. Ollama·OpenAI Chat Completions·Anthropic Messages의 요청/응답 변환을 가짜 응답과 loopback 테스트 서버로 검증했습니다. 실제 provider 호출·한국어 품질·메모리·과금은 미검증이며, 기존 RAG UI와 평가 runner의 연결은 후속 작업입니다. P013 보류는 계속됩니다.

[학습 시작점](README.md) · [지원 상태](models-and-support.md) · [구현](../../../rag_package/llm/core.py) · [검증 기록](../../verification/p025/README.md)

## 호출 없이 설정 확인

Python 3.10 이상과 표준 라이브러리만 필요합니다. 프로젝트의 `hr_rag_dev/` 루트에서 실행합니다. 현재 컴퓨터의 `python3`가 오래된 버전이면 기존 Python 3.10+ 실행 파일을 선택하세요. 검증 환경은 Python 3.12.14입니다. 새로운 의존성 설치가 필요하지 않습니다.

```sh
python3 -m rag_package.llm --help
python3 -m rag_package.llm validate --config examples/llm/local.json
python3 -m rag_package.llm validate --config examples/llm/openai.json
python3 -m rag_package.llm validate --config examples/llm/anthropic.json
python3 -m rag_package.llm preview --config examples/llm/anthropic.json --role generation --messages examples/llm/messages.json
```

`validate`는 설정 형식만 검사합니다. 모델 존재·digest·키 값이나 키 존재 여부를 조회하지 않습니다. `preview`는 provider에 보낼 본문과 실제 messages hash를 보여주며 네트워크·키에 접근하지 않습니다. 프롬프트/문서 내용이 표시되므로 공유 전에 확인하세요. import와 help도 모델을 호출하지 않습니다.

[local.json](../../../examples/llm/local.json)은 기존 잠금 파일의 qwen3:4b(Thinking-2507)와 qwen3:8b digest를 인용합니다. 현재 서버 가용성이나 P013 재개 승인을 의미하지 않습니다. [openai.json](../../../examples/llm/openai.json)과 [anthropic.json](../../../examples/llm/anthropic.json)은 실제 스키마를 통과하지만 `REPLACE_WITH_PROVIDER_MODEL_ID`를 사용자가 확인한 모델 ID로 바꿔야 합니다. 모델 이름·가격을 기본값으로 추측하지 않았습니다. [messages.json](../../../examples/llm/messages.json)은 가상 질문입니다.

P024의 [local 설계 예시](examples/local.json)와 [api 설계 예시](examples/api.json)는 `example_only` 문서로 보존했습니다. 실제 CLI는 이 파일을 거부합니다.

## 역할과 설정

`schema_version:1`, `profiles`, `roles`를 사용합니다. `roles.generation`과 `roles.evaluation`은 각각 profile 이름을 참조합니다. 같은 profile을 공유하거나 별도 모델을 선택할 수 있습니다. 추출·Faithfulness·Correctness의 프롬프트와 채점법은 상위 모듈의 책임이며 이 모듈이 자동으로 평가하지 않습니다.

| 항목 | 의미·검사 |
| --- | --- |
| mode / provider | local/ollama, api/openai_chat, api/anthropic_messages만 지원 |
| model / identity | 실행 모델 이름과 출처. 로컬 expected_digest는 전체 SHA256, hf_id·conversion 필수. source_revision 모르면 null, quantization·license_url·validation_status는 설명용 선택값 |
| API identity | requested_model은 model과 동일. revision_pinned는 boolean, revision은 문자열 또는 null. 고정했다고 표시하려면 실제 revision 필요 |
| base_url | 로컬은 숫자 loopback HTTP, API는 HTTPS. userinfo·query·fragment·제어문자·경로 traversal 거부 |
| max_output_tokens | 정수 1..32768. 모델의 실제 입력 문맥 한도와 별개 |
| timeout_seconds | 1..600초. HTTP 소켓 대기 제한. 전체 여러 단계의 wall budget을 대신하지 않음 |
| response_mode | text 또는 json_object. 임의 JSON Schema는 미지원 |
| api_key_env | API에서만 환경 변수 이름 필수. 키 값은 설정 파일에 넣지 않음 |
| temperature | 선택, null이면 생략. 0..2 범위 검사는 provider/model의 실제 지원을 보증하지 않음 |
| num_ctx / seed | Ollama만. num_ctx 512..131072, seed 0..2147483647 정수 |

미지정 schema 필드와 bool을 정수로 쓴 값, NaN/Infinity, 중복 JSON 키를 거부합니다. 입력 파일은 각각 2MiB, HTTP 응답은 4MiB까지입니다. messages는 문자열 content만 허용하며 선두 system 최대 1개, user/assistant 교대, 마지막 user입니다. 도구·이미지 입력을 자동으로 바꾸거나 버리지 않습니다.

임베딩·리랭커는 이 LLM 설정에 넣지 않습니다. 두 모드 모두 공개 모델 기본 방향을 유지하며 검색과 색인 설정은 후속 통합 계약에서 연결합니다.

## provider별 실제 전송

| provider | 전송과 처리 |
| --- | --- |
| Ollama | `/api/chat`, stream=false, think=false, keep_alive=0, options.num_predict. 호출 전후 `/api/tags` digest 대조. 사전 불일치면 생성 요청 0회, 사후 불일치면 성공 처리 안 함 |
| OpenAI Chat | `/chat/completions`, Bearer, max_completion_tokens, nonstream. n은 생략하고 기본 단일 응답 사용, 복수 choices는 거부 |
| Anthropic Messages | `/messages`, Bearer, anthropic-version=2026-10-21, max_tokens. 선두 system을 top-level로 이동 |

2026-11-27 확인한 공식 문서: [Ollama chat](https://docs.ollama.com/api/chat), [OpenAI Chat create](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [Claude Messages create](https://platform.claude.com/docs/en/api/http/messages/create). OpenAI의 출력 예산에는 reasoning 토큰도 포함될 수 있습니다. 모든 모델이 동일한 옵션을 지원한다고 가정하지 않습니다.

json_object는 공통 JSON 지시를 system에 추가하고 변경된 messages hash를 기록합니다. Ollama는 format=json, OpenAI는 response_format=json_object를 사용합니다. Anthropic은 지시와 로컬 JSON 검증을 사용하며 native schema 보장을 주장하지 않습니다. 중복 키·nonfinite 숫자·배열·Markdown fence는 거부하고 자동 복구하지 않습니다. 내용의 업무 schema는 호출자가 검증해야 합니다.

## invoke와 결과

아래는 CLI 문법 설명이며 **지금 실행하는 기본 실습이 아닙니다**. 실제 실행에는 별도로 모델/문서 전송·호출 한도·비용·중지 조건을 정해야 합니다. P013 보류나 기존 원장을 우회하는 명령으로 사용하지 마세요.

```text
python3 -m rag_package.llm invoke --config <개인 설정 파일> --role generation --messages <입력 파일> --output <새 결과 파일>
```

invoke 직전에 지정한 API 환경 변수 하나만 읽습니다. 키 누락·제어문자는 전송 전에 실패합니다. 기본 transport는 proxy를 사용하지 않으며 TLS 검증을 유지합니다. redirect·retry·provider fallback이 없습니다. 한 invoke의 생성 요청은 최대 1회입니다. Ollama의 digest 조회는 별도 metadata 요청입니다. timeout 뒤에는 전달·과금 여부가 불명일 수 있으므로 자동 재시도하지 않습니다.

결과에는 status, content, parsed_json, provider, requested_model/response_model, role, identity_verification, finish_reason, usage, elapsed_ms, request_fingerprint, error가 있습니다. API 응답 모델은 alias 때문에 요청 모델과 달라도 기록합니다. Ollama는 이름과 digest를 확인합니다. 누락 usage는 null, Ollama duration은 ns→ms, 비용은 null/unmeasured입니다. 실측 토큰과 비용을 혼동하지 마세요.

| status | 의미 |
| --- | --- |
| complete | 정상 종료·문자열 본문, JSON 모드는 strict object 검증까지 통과 |
| truncated | length / max_tokens 종료 |
| refused | refusal / content_filter |
| unsupported_response | 도구 요청·알 수 없는 블록/종료·thinking 위반 |
| invalid_response | envelope/role/model/done/본문 문제, 잘못된 JSON |
| error | 설정 이후 키·HTTP·연결·identity 등 호출 실패 |

complete 이외에는 본문과 parsed_json을 성공 답변으로 남기지 않습니다. Ollama think=false에도 nonempty thinking이 오면 거부합니다. Anthropic의 분리된 thinking/redacted_thinking 블록은 저장하지 않고 text만 처리합니다. 본문에 `<think>` 계열 태그가 섞이면 일부를 잘라 복구하지 않고 전체를 거부합니다. JSON 문자열 안의 태그도 보수적으로 거부합니다. 원문 provider body·hidden thinking·인증 헤더·예외 문자열은 결과에 저장하지 않습니다.

error code로 http_401/403/429, http_5xx, timeout, connection_error 등을 구분합니다. dispatch_attempted는 생성 전송을 시도했는지, outcome_unknown은 전송 단계 실패로 결과를 확신할 수 없는지를 나타냅니다. CLI는 validate/preview 성공 또는 invoke complete만 exit 0입니다. 나머지는 nonzero JSON 오류이며 기존 결과 파일을 덮어쓰지 않습니다. 새 파일은 임시 파일에서 원자적으로 공개합니다. 정상 content와 preview는 개인 문서를 포함할 수 있으므로 public artifact로 자동 저장하지 마세요.

## 검증 범위

```sh
python3 -m unittest discover -s tests/rag_package -v
```

테스트는 synthetic 키·주입 응답과 테스트 소유 loopback 서버만 사용합니다. socket guard가 그 서버 이외 연결을 막고 실제 사용자 API 키를 조회하지 않습니다. 가짜 서버 시작 권한이 제한된 환경에서는 해당 시험을 허용된 환경에서 실행해야 합니다. 실제 Ollama 서버는 시작하지 않습니다.

오프라인 PASS는 모델 정확도·메모리 PASS나 API 실연결 성공을 뜻하지 않습니다. Google Drive·RAG UI provider 선택·기존 평가 runner 통합·Responses API·streaming·tools·multimodal은 이번 모듈 범위 밖입니다.
