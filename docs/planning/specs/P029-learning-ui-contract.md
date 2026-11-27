# P029 학습 UI 실행 계약 v1

이 계약은 [화면 설계](P029-learning-ui-design.md)의 준비 미결 항목을 고정한다. P028 완료 후 실행하며 P008 평가 UI와 P010/P020 선행 변경을 대신하지 않는다. source checkout과 설치 wheel 모두 동일한 실제 P025~P028 코어를 호출한다. 아래 검증에서는 실제 모델/Drive/계정 호출 없이 주입 backend만 사용한다.

## 경로·실행·등록

`rag_package/ui_server.py`, `rag_package/ui/` static resources, 필요한 UI registry/job 모듈, tests/rag_package, docs/learning/rag-package/ui.md, docs/verification/p029를 추가한다. 기존 단계 server/UI와 P013 기록은 유지한다. 순수 디자인/구조를 가져오면 원본 commit/path/hash를 provenance에 기록한다. frontend는 HTML/CSS/vanilla JS와 로컬 assets로 구현하며 외부 CDN/telemetry가 없다.

`rag-lab serve --workspace DIR [--sources FILE] --llm-config FILE [--llm-config FILE...] [--drive-config FILE...] [--port PORT] [--allow-model-execution] [--allow-drive-download]`와 module CLI가 같은 server를 시작한다. 기본 host는 변경 불가능한 127.0.0.1, port8765. port0(검증용 OS 선택), 또는1024..65535 지원. 충돌이면 명확히 실패하며 다른 서버를 종료하거나 port를 조용히 바꾸지 않는다. 브라우저 자동 실행은 하지 않는다. 두 allow flag는 기본 false이며 production 실제 호출을 허용하는 별도 서버 시작 옵션이다. 이번 dev 검증에서는 actual provider/Drive 호출을 하지 않는다.

workspace는 명시한 기존 실제 디렉터리다. sources/LLM/Drive config 파일과 sources가 가리키는 원본은 resolve 후 workspace 안에 있어야 하며 symlink 경로를 거부한다. config 파일당1MiB/등록 LLM1..8개/Drive0..4개. P025/P027 strict schema 검증으로 등록한다. 예시 미설정 LLM도 preview에는 등록하되 configuration_required로 표시한다. API secret/credential 내용은 등록이나 화면 조회 시 읽지 않는다. sources가 없으면 빈 문서 목록으로 시작해 업로드할 수 있다. sample 등록 명령은 P028 init이 실제 생성한 경로를 사용해 문서에 적는다.

server 시작 시 각 config의 bytes/hash와 승인된 원본 경로 목록을 session registry에 고정하고 opaque ID로 노출한다. browser는 ID만 사용하며 path/임의 endpoint/명령을 보낼 수 없다. workspace 밖 원본·설정이 필요하면 사용자가 명시적으로 실습 workspace 안에 복사한다. 실제 OAuth credential은 P027/P028 규칙대로 workspace/Git 밖에 두며 Drive config만 workspace 안에서 그 경로를 참조한다. 기존 config file 변경을 자동 반영하지 않고 재시작/새 session으로 명확히 갱신한다.

UI 기록은 workspace/.rag-runs/ui 아래 불변 job/result 디렉터리와 registry로 둔다. raw token/키/credential file 내용/Authorization/resourcekey/전체 원래 Drive URL은 logs/job metadata/API 응답에 저장하지 않는다. 실행용 private config에 원래 Drive link가 필요하면 P027 입력 config의 고정된 in-memory 사본으로만 사용하고 job에는 redacted identity/hash만 보관한다. 서버 재시작은 Drive job를 재실행하지 않는다. 일반 source 원문·질문·답변은 본래 private artifact일 수 있음을 안내하며 Git 제외한다.

## HTTP 경계와 schema

고정 loopback Host(선택 port 포함)를 검증한다. GET/POST 모두 Origin이 있으면 정확 same-origin만 허용한다. CORS wildcard 없음, JSON POST와 upload에는 시작 시 생성한 session token `X-Rag-Session`을 요구한다. token은 same-origin bootstrap 응답으로만 전달하며 URL/query/localStorage에 넣지 않는다. static/API는 no-store, nosniff, CSP self-only(script/style/connect), object-src none, frame-ancestors none를 적용한다. 원문/모델 출력은 textContent로 표시하고 innerHTML/raw Markdown 실행에 넣지 않는다. static 파일은 고정 allowlist이며 directory listing/path traversal/symlink를 차단한다. 요청 로그는 원문/URL query/headers를 남기지 않는다.

JSON은 P025 strict decoder로 중복키/nonfinite/추가 필드를 거부한다. JSON body≤16KiB, Content-Length 필수이고 유효 범위 아니면 읽기 전에 거부한다. transfer-encoding은 지원하지 않는다. 각 API는 `{schema_version:1,status,data}` 또는 `{schema_version:1,status:"error",error:{code,stage}}` JSON을 반환한다. 민감한 raw exception은 출력하지 않는다. 400 invalid,403 origin/token,404 unknown ID,409 conflict/stale,413 limit,429 busy,500 sanitized internal failure.

| endpoint | 입력/응답의 핵심 |
| --- | --- |
| GET /api/bootstrap | session token, registered docs/config IDs의 sanitized 요약, 지원 capability, allow flags, limits, 최근 job 요약. secret·원래 Drive URL 없음 |
| POST /api/uploads/{pdf\|txt\|md} | application/octet-stream, Content-Length≤20MiB, X-File-Name은 encodeURIComponent된 UTF-8 표시 이름≤200자. decoded basename을 표시만 하고 실제 파일명은 서버 UUID. 응답 input_id |
| POST /api/jobs | 아래 kind별 strict 요청, UUID request_id. 응답202 job_id/status 또는 같은 요청의 기존 job |
| GET /api/jobs/{id} | 상태·현재 단계·완료 artifact ID·sanitized failure/dispatch 정보, 실제 호출 여부 |
| GET /api/artifacts/{id} | 검증된 manifest/요약과 type별 페이지/청크/답변/비교 링크. arbitrary 파일 내용 endpoint 아님 |
| GET /api/artifacts/{id}/pages?document_id=...&page=N&offset=N&limit=N | canonical page의 최대8000자 window와 원래 offset/페이지/정규화 정보. limit1..8000. 반환 텍스트를 요약/변형하지 않음 |
| GET /api/artifacts/{id}/chunks?offset=N&limit=N | 최대100청크 목록/원문slice/page/heading metadata와 next offset |
| GET /api/artifacts/{id}/original?document_id=... | 검증·등록된 원본만 attachment로 다운로드. HTML로 inline 실행하지 않음 |

upload의 empty/unsupported/잘못된 UTF-8/크기 초과는 정확한 오류로 표시하고 성공한 snapshot이라고 표현하지 않는다. parse는 별도 snapshot job에서 P026 한도/needs_review를 적용한다. session input 최대20개, 중간 실패 파일은 artifact로 등록하지 않는다. 파일 이름에 경로/제어문자/스크립트가 있어도 storage 경로나 실행에 쓰이지 않는다. 서버는 20MiB를 넘겨 무제한 read하지 않는다. body/read timeout30초.

## Job 입력과 상태

모든 job 공통: `request_id` UUID와 `kind`, 해당 kind의 허용 필드만 받는다.

- snapshot: input_ids1..20. 등록된 sample/upload 원본만 sources로 묶어 P026 snapshot 수행.
- drive_preview: drive_config_id, url(최대2048자). 등록된 auth만 재사용해 사용자가 화면에 입력한 링크를 P027 strict parser로 검증한다. SDK/credential/HTTP0. 응답에는 resourcekey/원래 URL을 되돌리지 않는다.
- drive_pull: drive_config_id, url(최대2048자). 등록 auth + strict URL을 memory config로 합성한다. allow-drive-download=true인 server에서 사용자가 실행한 경우만 P027 execute, 결과 snapshot을 registry에 연결.
- build: snapshot_id, chunking{method,size_chars,overlap_chars}, retrieval{method,top_k,context_budget_chars}, llm_config_id. P026 schema/bounds 그대로.
- ask: build_id, llm_config_id, question(1..2000자), top_k, context_budget_chars, execute(bool; default false). build와 청킹/검색 identity를 유지하고 허용 query 설정만 바꾼다. execute=true는 allow-model-execution=true인 server와 configured profile 필요. preview 후 실제 실행도 새로운 job이며 변경된 입력은 새 preview로 표시한다.
- compare: snapshot_id, variants2..4(각각 label,chunking,retrieval,llm_config_id), questions1..20({id,question}), execute(default false). 최대80 generation 요청, 현재 P026 limits와 동일. 같은 snapshot/questions를 고정하고 changed_axes/모든 실패 행을 보존한다.

source/build/answer/comparison artifact는 P026/P027 schema와 hash를 검증해서만 등록/조회한다. 요청에서 output 경로를 받지 않으며 server가 새 UUID 경로를 정한다. schema·kind·context 조회 endpoint의 정확 ID format은 모든 routes와 registry에서 일관되게 검증한다. source/config/등록 artifact 변조는 stale 오류로 실패하고 자동 rebuild하지 않는다.

동시 실행은1개, 대기열은 두지 않는다. busy 때 새 요청은429이며 UI가 ‘현재 작업 종료 후 다시 실행’으로 표시한다. 같은 request_id+동일 정규화 payload hash는 기존 job을 반환하며 같은 id+다른 payload는409다. idempotency 상태를 durable하게 저장해 refresh/재시작 뒤 같은 요청을 다시 실행하지 않는다. UI가 polling 실패 시 POST를 자동 재전송하거나 새로운 request_id를 생성하지 않는다.

상태는 queued(단기 저장 직후), running, completed, needs_review, failed, interrupted. 완료 점수는 만들지 않는다. 작업 제출 시 입력/config/source fingerprint를 고정한다. API에 ‘accepted’가 반환되기 전에 job 기록을 durable하게 남긴다. worker는 코어 함수를 호출하고 상태·결과 저장/atomic publish 오류를 실패로 기록하며 자동 재시도하지 않는다. response 저장이 실패해도 dispatch_attempted를 보존한다. hard process crash로 확인할 수 없는 경우 unknown을 허용하며 false로 단정하지 않는다.

재시작 시 queued/running을 interrupted로 기록하고 자동 실행하지 않는다. 이전 session job 조회는 가능하지만 raw secret/config를 복원해 실행하지 않는다. 중단 버튼은 이번 버전에 제공하지 않는다. 페이지 닫기는 작업 중지가 아니며 UI에 이를 표시한다. 서버를 종료할 때도 외부 모델 요청 취소가 보장된다고 주장하지 않는다. UI는 terminal job의 원문/결과를 다시 볼 수 있어야 한다.

## 화면과 상호작용

상단에 ‘일반 문서 RAG 실험실’, 현재 문서 snapshot, preview/live/test_fixture 표시를 둔다. 0문서/1모델/2청킹/3검색/4답변/5비교 tab 또는 단계 navigator. layout은 원문·결과 중심이고 내부 JSON·SHA·긴 로그는 details 기본 접힘. 원문 인용은 읽을 수 있게 기본 표시한다. 상태는 글자+아이콘으로 표시하고 색만으로 구분하지 않는다. keyboard focus, label/aria 상태, skip link를 제공한다.

문서는 sample/업로드/Drive 링크 직접 입력 중 선택하고 preview/pull 버튼을 구분한다. 사용자는 붙여넣은 링크와 서버 시작 시 등록한 인증 profile을 선택한다. 새 credential/외부 host를 웹 입력으로 추가하지 않는다. 지원 Google Drive 링크만 P027 parser를 거쳐 고정 API로 연결하며 다른 웹하드는 미지원 이유를 표시한다. resourcekey가 있는 원래 URL은 사용자가 입력한 현재 form에서만 유지하고 browser URL/localStorage/server durable request에 저장하지 않는다.

모델 목록은 등록 LLM profiles의 provider/model/HF ID와 사용자 설정 필요 여부를 보여 준다. API key 입력창은 만들지 않는다. 아래 설정 form으로 모델명·generation 설정을 편집해 새 config를 저장/선택/비교할 수 있다. 기존 profile을 덮어쓰지 않는다. 기본값은 local이며 API는 명시 선택한다. 실행 불가능한 placeholder는 이유와 설정 안내를 보여 준다. 가능한 두 모델 설정으로 preview comparison을 실제 코어에 전달할 수 있어야 한다.

청킹은 fixed/recursive/structure와 숫자 입력을 별개로 둔다. 긴 섹션 재분할/heading metadata를 설명하고 선택 청크에서 해당 원문 페이지/offset으로 이동한다. size/top-k/검색 근거 최대 분량(문자)/모델 token window를 별도 설명하며 문자→토큰 정확 환산을 발명하지 않는다.

검색과 답변 화면은 후보 top-k, 실제 포함, budget 제외를 나란히 표시한다. 질문 입력 후 기본 ‘검색·입력 미리보기’, 별도 ‘실제 답변 생성’이다. 실제 버튼은 server flag/config 조건을 만족할 때만 활성화되며 모델/API와 전송문맥·최대1요청을 바로 옆에 표시한다. 이미 승인한 사용자의 클릭을 반복 modal 승인으로 막지 않는다. 생성 결과 answered/abstained/failed를 정확히 보여 주고 validated citation의 원문·페이지로 이동한다.

비교는 설정2~4, 질문1~20 선택/입력으로 P026 compare를 실제 호출한다. 결과는 각 행의 상태/바뀐 축/검색·전달 문맥·답변/지연/usage/비용 미측정을 표시한다. preview는 답변/품질 점수가 없음을 명확히 보여 준다. evaluator/qrels 미연결 값은 N/A 이유를 한국어로 보여 준다. 실패행/누락 결과를 숨기지 않는다.

미구현 Dense/Hybrid/임베딩 선택/리랭커/semantic·LLM 청킹/평가기 옵션은 disabled와 이유를 표시한다. P007 전용 실험으로 이동할 안내는 별도 링크/명령이며 해당 서버를 자동 시작하지 않는다. 이 UI 증분은 전체 feature goal 완료가 아니다.


## 직접 링크·모델 설정 form의 추가 계약

Drive job 요청은 raw URL을 memory에서만 가지고 P027 strict parser/config validation을 사용한다. P027 connector가 파일 경로만 받는 경우, 기존 path API를 보존하는 typed config/validated-memory 진입점을 추가하여 서버가 URL/resourcekey를 임시 JSON 파일로 쓰지 않아도 호출할 수 있게 한다. raw HTTP request를 그대로 job log에 저장하지 않는다. idempotency hash는 전체 정규화 입력을 반영하되 durable 요청 요약에는 config_id와 redacted link identity만 기록한다. 재시작 후 interrupted job는 자동 복원/실행하지 않는다. 이 수정은 P027 실제 다운로드/정확 version/secret/실패 계약을 유지하는 UI adapter 범위이며 fake production 경로가 아니다.

POST /api/model-configs는 `{base_config_id, model, max_output_tokens, temperature, local_identity?}`를 받는다. 기본 server에 등록된 config의 generation profile만 복제하며 provider/base_url/key_env/auth/timeout/응답 schema와 evaluation profile은 browser가 바꾸지 못한다. generation과 evaluation이 같은 profile이면 별도 generation profile을 만들어 role mapping을 분리한다. model은1..200자, 나머지 한도는 P025 validator를 그대로 사용한다. local_identity는 local일 때만 `{expected_digest,hf_id,source_revision,quantization}`를 받으며 digest64hex/HF repository 형식과 필요한 값을 검증한다. local model/HF ID를 바꿀 때 과거 변환·라이선스 검증 metadata를 승계하지 않는다. conversion은 user-configured/unverified로 표시하고 기존 license_url은 제거한다(별도 라이선스 검토 전). API에서는 이 필드를 거부하고 requested_model을 새 model에 맞추며 revision_pinned=false/revision=null로 명시한다. 새 model 변경을 원래 pinned revision 검증으로 표시하지 않는다.

UI는 기본 model·출력 길이·temperature 입력과 advanced local digest/HF 출처를 제공한다. Ollama alias만으로 HF model identity를 자동 추측하지 않는다. digest/HF 경로를 찾는 명령은 안내하되 이 form 저장은 서버/모델 조회·key env 읽기·다운로드·API 호출을 하지 않는다. example 값/0 digest/EXAMPLE_ model은 실제 설정 완료로 저장하지 않는다. 성공하면 validation_status=user_configured_unverified이고 live success 배지가 아니다. API endpoint/key env를 바꾸려면 사용자가 CLI에서 새 profile을 등록해야 한다.

새 config는 workspace/.rag-runs/ui/configs의 불변 서버 ID 파일로 저장하고 전체 strict validation/bytes hash 후 registry에 추가한다. 최대 등록 config는 base+UI생성 합계8개다. 응답은 새 opaque config_id와 sanitized summary뿐이다. GET /api/model-configs/{id}/export는 secret 없는 config JSON을 attachment로 제공한다. 모든 새로운 endpoint도 same-origin/session token·입력한도·추가필드 금지·경로 registry 규칙을 따른다. 질문/문서/Drive resourcekey나 실제키가 config export에 들어가지 않아야 한다. 기존 질문·청킹 조건을 고정한 채 두 생성 config를 비교해 모델 선택 학습을 할 수 있어야 한다.

추가 시험은 typed Drive URL preview/pull 성공·위장 호스트/resourcekey 비노출·memory path/source API 호환, local/API config clone·shared role 분리·endpoint/key-env 변경 거부·불변 저장/재시작 조회·export secret sentinel·placeholder거부·서버 조회0·두 모델 compare다. 실제 browser에서도 직접 링크 form과 model form의 labels/validation/errors를 확인한다. 실계정/모델 호출은 fake backend로 대체하고 execution_kind 표시를 유지한다.

## 검증·실행 권한

허용: 새 local server(127.0.0.1 임의 port)와 합성 문서, fake model/Drive auth/HTTP backend, browser용 격리 테스트 자산/필요한 공식 테스트 의존성 설치. 기존 사용자 서버를 종료/변경하지 않는다. 금지: 실제 모델/API/키/OAuth/계정/문서 접근, 모델 다운로드/서버 시작, P013 grant 소비, public server 배포. production config에 fake backend 옵션을 노출하지 않고 테스트가 주입한 실행은 test_fixture가 UI/결과 모두에 나타난다.

핵심 독립 기대값: 문서 업로드→snapshot→세 chunker/build→BM25 preview→원문 locate, 같은 두 config 비교의 모든 행, fake successful answer의 정확 원문 인용, invalid citation/neutral N/A/needs_review/empty context/placeholder 오류, Drive preview와 fake pull→snapshot. 실제 코어 호출 여부와 모델 dispatch 횟수0/1/중복0을 검증한다. 서버 origin/token/path/XSS/큰 body·chunk 조회limit·symlink·config/artifact tamper·job duplicate/busy/restart/쓰기실패를 시험한다.

실제 browser에서 desktop(약1280폭), narrow(약390폭), keyboard Tab/Enter/Space, loading/empty/error/장문 quote wrap/기본접힘로그/원문 locate와 비교를 관찰한다. 실제 도구 정책이 허용하는 browser surface만 사용한다. 접근이 거부되면 다른 도구/URL로 정책을 우회하지 않고 해당 실제 관찰을 미완료로 남긴다. 기존 run004 사람 확인을 새 UI 승인으로 재사용하지 않는다. browser 실행은 test_fixture이므로 live 품질/계정 연결을 증명하지 않는다.

P028 wheel-only clean venv/source 없는 cwd에서 assets 포함과 serve 동작을 확인한다. P025~P028 회귀, 기존 stage/GT/P013 hash 보존, dependency/resource provenance와 local 링크를 검증한다. docs/verification/p029에 commands/실제 화면 관찰·테스트 결과·한계·port/검증 서버 종료 상태·실행 로그를 남기고 dev 완료 기준/normal personal-dev push를 따른다. 실제 관찰이 미완료면 C4를 체크하지 않는다. main은 변경하지 않는다.
