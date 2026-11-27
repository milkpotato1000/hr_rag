# 문서 RAG 실습 시작

이 폴더는 합성 문서 실습용입니다. 실제 회사 규정이 아닙니다. 기본은 모델·API·키·Drive를 사용하지 않는 preview입니다. Python 3.10+, macOS/Linux storage primitive가 필요합니다. 같은 Mac의 새 venv만 검증했고 Linux/두 코딩 도구 UI는 미검증입니다.

```sh
rag-lab --version
rag-lab doctor
rag-lab doctor --config fixed.json
```

doctor의 exit 3/needs_configuration은 샘플 모델이 미설정이라는 뜻입니다. 아래 preview는 그대로 실행할 수 있습니다. live_checks는 항상 not_checked입니다.

```sh
rag-lab snapshot --sources sources.json --out .rag-runs/snapshot-01
rag-lab build --snapshot .rag-runs/snapshot-01 --config fixed.json --out .rag-runs/fixed-01
rag-lab ask --run .rag-runs/fixed-01 --config fixed.json --question '생일 휴가 자격과 신청 기한은?' --out .rag-runs/answer-01
rag-lab compare --snapshot .rag-runs/snapshot-01 --configs fixed.json recursive.json structure.json --questions questions.json --out .rag-runs/compare-01
```

원문→청크→검색 후보→전달 예정 문맥을 산출물에서 대조하세요. 청킹 방식/크기/중첩을 한 번에 하나씩 바꾸고 새 경로를 쓰세요. 답변 생성과 품질 점수는 아직 미측정입니다. Dense/Hybrid RRF·CrossEncoder 리랭커·의미/LLM 청킹도 지원합니다. 아래 등록 설정과 명시 실행 권한이 필요하며, 실제 한국어 모델 품질은 미검증입니다.

## 본인 모델 설정

llm-local.json은 EXAMPLE_OLLAMA_MODEL, 0으로 채운 digest, HF 후보만 들어 있습니다. 본인 모델명과 실제 digest, HF 원본/revision·변환 정보를 입력하고 identity.validation_status를 user_configured_unverified로 바꾸세요. 자동 모델 조회·교체·다운로드는 하지 않습니다. 잘못된 digest는 실행 시 거부됩니다. API를 선택하려면 llm-api.json의 실제 API model/requested_model과 validation_status를 바꾸고 RAG 설정의 llm_config를 그 파일로 지정하세요. 키 값은 파일/CLI/Git에 넣지 말고 api_key_env가 가리키는 환경 변수로 관리합니다. 코딩 도구 구독은 API 이용권이 아닙니다.

실제 답변은 전송 문서·provider·비용/호출 상한을 정한 사용자가 ask에 --execute를 추가할 때만 요청합니다. API에는 질문과 선택 문맥이 전송되며 비용은 미측정입니다. 자동 재시도/대체 모델은 없습니다. evaluation role은 이 실습에서 호출하지 않습니다.

## 문서·Drive와 보관

문서 경로는 sources.json 기준이며 synthetic는 실제 원문이면 false로 관리하세요. PDF는 pdf extra가 필요하고 스캔/OCR/암호 PDF는 지원하지 않습니다. Drive 샘플은 가짜 ID입니다. 실제 pull은 별도 인증과 명시 --execute가 필요하며 drive.readonly는 선택 파일 하나보다 넓은 권한입니다. OAuth client/credential은 이 실습 폴더 및 모든 Git 저장소 밖의 전용0700디렉터리/0600파일에 둡니다. 실제 문서/산출물은 공개 Git에 넣지 마세요. .rag-runs는 제외되며 기존 출력은 덮어쓰지 않습니다.

## 코딩 도구 요청

Codex: “현재 폴더와 상위 AGENTS.md 규칙을 읽고, START_HERE.md의 preview 실습만 실행해줘. 청킹 한 변수의 차이와 후보/전달 문맥을 설명해줘. 모델/API/Drive 호출과 설치·서버 시작은 하지 마.”

Claude Code: “현재 폴더와 상위 CLAUDE.md/AGENTS.md 규칙을 읽고, 같은 rag-lab preview 실습을 실행해줘. 결과 파일과 미측정 지표를 설명해줘. 실제 모델/API/Drive 호출은 하지 마.”

두 요청은 공통 CLI 구조를 사용합니다. 두 제품 UI를 자동 검증한 것은 아닙니다. init은 Git/harness/도구를 설치하거나 기존 규칙을 덮어쓰지 않습니다. 소스 라이선스는 별도 허가를 확인해야 하며 공개 모델의 라이선스와 같지 않습니다.

## 다섯 청킹 방식과 저장 경계

chunk-fixed/recursive/structure/semantic/llm.json은 청킹 전용 설정입니다. 기존 fixed.json 등은 v1 RAG 설정으로 계속 작동합니다.

```sh
rag-lab chunk --snapshot .rag-runs/snapshot-01 --config chunk-fixed.json --out .rag-runs/chunk-fixed
rag-lab chunk-replay --run .rag-runs/chunk-fixed
rag-lab build --snapshot .rag-runs/snapshot-01 --config rag-frozen.json --out .rag-runs/frozen-index
rag-lab ask --run .rag-runs/frozen-index --config rag-frozen.json --question '생일 휴가 자격은?' --out .rag-runs/frozen-answer
rag-lab chunk --snapshot .rag-runs/snapshot-01 --config chunk-semantic.json --out .rag-runs/semantic-preview
rag-lab chunk --snapshot .rag-runs/snapshot-01 --config chunk-llm.json --out .rag-runs/llm-preview
```

의미/LLM은 위 명령에서 실제 호출 0회입니다. 실제 경계 생성은 설정을 준비하고 새 출력 경로에 --execute-chunking을 명시해야 합니다. LLM 설정 schema v2의 chunking 역할은 generation/evaluation과 독립입니다. 공유 프로필을 UI에서 생성용으로 복제해도 청킹 역할은 보존합니다.

단위는 원문의 공백·줄바꿈·Unicode codepoint를 보존합니다. 의미 청킹은 단위 임베딩의 이웃 거리로 경계를 고르고, LLM은 마지막 단위 ID만 고릅니다. 청크 본문은 항상 원문 slice입니다. 단위 임베딩을 검색용 청크 임베딩으로 재사용하지 않습니다. 최대 문자/요청 byte는 모델 token window의 보장이 아닙니다.

chunk-derive는 저장 단위/경계로 overlap 등을 바꾸며 모델 호출이 없습니다. LLM 파생은 원래 경계를 유지합니다. 새 최대 크기를 넘으면 실패합니다. 비교하려면 각 저장 청크를 가리키는 rag-frozen.json 사본 2~5개를 만들고 compare에 넘기세요. 검색/생성 설정과 원문은 동일해야 합니다. --facts는 원문 span 기준 필수 근거 회수용이며 청크 ID 정답을 다른 청킹에 복사하지 않습니다. chunk-report는 저장 비교를 모델 없이 검증합니다.

## 검색·리랭킹과 학습 화면

rag-hybrid.json / embedding-e5.json은 공개 모델의 로컬 파일·revision·전체 SHA256 manifest 준비가 필요한 예시입니다. retrieval-preview는 모델을 읽지 않습니다. Dense/Hybrid build/ask는 --execute-retrieval, rerank는 --execute-reranking, 생성은 --execute가 각각 필요합니다. reranker-bge.json도 미설정 예시입니다. 자동 다운로드/서버 시작/유료 호출은 하지 않습니다.

```sh
rag-lab retrieval-preview --config rag-hybrid.json
rag-lab serve --workspace . --sources sources.json --llm-config llm-local.json --chunk-config chunk-fixed.json --chunk-config chunk-recursive.json --chunk-config chunk-structure.json --chunk-config chunk-semantic.json --chunk-config chunk-llm.json
```

serve는 사용자 명시 실행 시 localhost 학습 서버를 시작합니다. 기본 모델 실행 권한은 모두 꺼져 있습니다. 허용 옵션은 --allow-chunking-execution / --allow-retrieval-execution / --allow-reranking-execution / --allow-model-execution으로 분리됩니다. 임베딩은 --embedding-config, 리랭커는 --reranker-config, 원문 정답은 --facts로 서버에 등록하세요. 브라우저는 등록 ID만 선택하며 endpoint·키 환경 변수·인증 경로를 수정하지 않습니다.
