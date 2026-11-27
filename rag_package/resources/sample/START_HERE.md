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

원문→청크→검색 후보→전달 예정 문맥을 산출물에서 대조하세요. 청킹 방식/크기/중첩을 한 번에 하나씩 바꾸고 새 경로를 쓰세요. 답변 생성과 품질 점수는 아직 미측정입니다. Dense/Hybrid/리랭커/의미·LLM 청킹은 이 경로에서 미지원입니다.

## 본인 모델 설정

llm-local.json은 EXAMPLE_OLLAMA_MODEL, 0으로 채운 digest, HF 후보만 들어 있습니다. 본인 모델명과 실제 digest, HF 원본/revision·변환 정보를 입력하고 identity.validation_status를 user_configured_unverified로 바꾸세요. 자동 모델 조회·교체·다운로드는 하지 않습니다. 잘못된 digest는 실행 시 거부됩니다. API를 선택하려면 llm-api.json의 실제 API model/requested_model과 validation_status를 바꾸고 RAG 설정의 llm_config를 그 파일로 지정하세요. 키 값은 파일/CLI/Git에 넣지 말고 api_key_env가 가리키는 환경 변수로 관리합니다. 코딩 도구 구독은 API 이용권이 아닙니다.

실제 답변은 전송 문서·provider·비용/호출 상한을 정한 사용자가 ask에 --execute를 추가할 때만 요청합니다. API에는 질문과 선택 문맥이 전송되며 비용은 미측정입니다. 자동 재시도/대체 모델은 없습니다. evaluation role은 이 실습에서 호출하지 않습니다. 기존 P013 보류·grant는 그대로입니다.

## 문서·Drive와 보관

문서 경로는 sources.json 기준이며 synthetic는 실제 원문이면 false로 관리하세요. PDF는 pdf extra가 필요하고 스캔/OCR/암호 PDF는 지원하지 않습니다. Drive 샘플은 가짜 ID입니다. 실제 pull은 별도 인증과 명시 --execute가 필요하며 drive.readonly는 선택 파일 하나보다 넓은 권한입니다. OAuth client/credential은 이 실습 폴더 및 모든 Git 저장소 밖의 전용0700디렉터리/0600파일에 둡니다. 실제 문서/산출물은 공개 Git에 넣지 마세요. .rag-runs는 제외되며 기존 출력은 덮어쓰지 않습니다.

## 코딩 도구 요청

Codex: “현재 폴더와 상위 AGENTS.md 규칙을 읽고, START_HERE.md의 preview 실습만 실행해줘. 청킹 한 변수의 차이와 후보/전달 문맥을 설명해줘. 모델/API/Drive 호출과 설치·서버 시작은 하지 마.”

Claude Code: “현재 폴더와 상위 CLAUDE.md/AGENTS.md 규칙을 읽고, 같은 rag-lab preview 실습을 실행해줘. 결과 파일과 미측정 지표를 설명해줘. 실제 모델/API/Drive 호출은 하지 마.”

두 요청은 공통 CLI 구조를 사용합니다. 두 제품 UI를 자동 검증한 것은 아닙니다. init은 Git/harness/도구를 설치하거나 기존 규칙을 덮어쓰지 않습니다. 소스 라이선스는 별도 허가를 확인해야 하며 공개 모델의 라이선스와 같지 않습니다.
