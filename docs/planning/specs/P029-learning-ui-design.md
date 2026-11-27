# P029 학습 화면 설계 초안

DRAFT. 현재 일반 문서 CLI 결과와 기존 고정 corpus 화면의 차이를 읽고 요구를 정리한 문서다. P028 완료 API·resource·설치 방법을 확인하고 서버/화면의 정확 계약·검증 수단을 확정한 뒤 READY로 전환한다. 실제 구현 허가는 아니다.

## 사용자 흐름

| 화면 | 사용자가 하는 일 | 기본으로 보여 줄 결과 |
| --- | --- | --- |
| 0. 문서 | 합성 샘플, 로컬 PDF/TXT/MD 업로드 또는 지원 Drive 링크 선택 | 실제/가상 문서 구분, 수집 상태, 버전·페이지, 추출 원문 |
| 1. 모델 | local Ollama 또는 본인 유료 API의 등록 설정 선택 | provider/model/HF 출처, 미설정 항목, 전송 대상·비용 미측정, live 미검증 |
| 2. 청킹 | 방식과 크기·오버랩 설정, 새 snapshot/build 실행 | 청크 수·길이 분포, 선택 청크→원문 위치, 긴 섹션 재분할과 제목 metadata |
| 3. 검색 | 질문, 검색 방법, top-k와 검색 근거 최대 분량 설정 | 순위 후보·선택·예산 제외를 분리, 검색 score와 정답률 구분 |
| 4. 답변 | 기본 preview 확인 후 실제 생성 명시 실행 | 실제 전달 문맥, 답변/보류/실패, 코드 원문 인용, 지연·usage/비용 N/A |
| 5. 비교 | 같은 문서·질문에 설정2~4개 선택 | 모든 행·실패 포함, 바뀐 축, 원문/설정 fingerprint, 미평가 지표 N/A |

한 번의 설정 변경이 실행을 자동 시작하지 않는다. 첫 실습은 키·모델 호출 없이 검색까지 끝낸다. 실제 답변이 없는 preview를 가짜 모범 답변으로 채우지 않는다. 각 단계에 ‘어떤 설정을 바꾸는지/무엇을 관찰할지’ 한 문장 설명과 세부 펼치기를 둔다. 내부 SHA/원시 JSON/긴 로그는 세부 정보에 두고 학습 기본 화면을 가리지 않는다.

## 기존 화면과 재사용

P007/P017의 `2. Document Chunking/web_chunking`은 23페이지 고정 규정집·source-v4와 고정 실행 ledger/평가를 전제로 한다. 그 server의 allowlist를 일반 문서에 맞게 느슨하게 바꾸지 않는다. 새 일반 UI는 설치 wheel의 `rag_package` resource와 실제 P025~P028 코어를 사용한다. 기존 Naive LangChain 기본 화면/실험 메뉴와 서버는 그대로 보존하고, 실행 시 별도 loopback port를 사용한다. 기존8000/8001/8003 서버를 자동 시작·종료하지 않는다.

색·레이아웃/원문→청크 locate 상호작용 등 순수 UI 요소를 선별 재사용하면 provenance를 남긴다. 원문·모델 응답·제목은 textContent 등으로 표시하며 HTML/Markdown raw 실행을 허용하지 않는다. 원문에 섞인 지시를 시스템 명령/모델 권한으로 취급하지 않는다. 외부 CDN/font/telemetry가 없는 로컬 UI를 기본으로 한다.

## 설정과 지원 목록

실제 validated configuration이 capability의 기준이다. 현재 지원은 local/API LLM profiles, 규칙 청킹 fixed/recursive/structure와 BM25다. Dense/Hybrid, embedding selector, reranker on/off, semantic/LLM 청킹, 평가기는 후속 구현 상태를 표시한다. 사용 가능한 것처럼 클릭되거나 BM25로 조용히 fallback하지 않는다. 기능 확장 때 UI와 CLI가 동일 schema를 공유한다.

모델 선택은 먼저 workspace에 등록·검증한 P025 profiles에서 한다. 새 사용자에게는 P028 예시 미설정 상태와 해결 안내를 보여 준다. local HF 원본/변환 runtime/digest와 API requested model/revision을 구분한다. API secret은 서버 환경변수 또는 저장소 밖 승인된 설정에서만 읽고 브라우저 입력/응답/URL/localStorage에 저장하지 않는다. 서버의 환경 전체를 조회하는 endpoint는 만들지 않는다. API key env ‘이름’은 표시 가능하지만 실제값은 아니다. GPU/메모리 실행 검증이 없으면 ‘추천으로 성능 보장’ 같은 배지를 붙이지 않는다.

Drive OAuth는 CLI에서 사용자 본인이 완료한 credential을 서버 시작 시 명시 등록하는 방식부터 검토한다. 웹 요청이 임의 파일 경로를 읽거나 임의 계정으로 로그인하지 않게 한다. 링크 preview와 실제 다운로드를 분리하고 read-only scope·지원 형식을 안내한다. resourcekey를 브라우저 URL query나 durable 로그에 복사하지 않는다. 다운로드 실패 후 자동 재요청하지 않는다.

## 서버·작업 경계 (준비 검토에서 고정)

`rag-lab serve --workspace DIR --port ...` 형태의 loopback-only 서버를 제안한다. UI는 명시 workspace 아래 등록된 input/config/artifact ID만 접근한다. arbitrary OS path·directory listing·shell command·외부 endpoint를 HTTP body로 받지 않는다. 업로드는 파일 수/byte/MIME 상한을 P026에 맞추며 filename을 서버 경로로 그대로 쓰지 않는다. 원본 다운로드는 등록된 artifact ID의 명시 endpoint로 제공한다.

Host/Origin 검증, session CSRF token, 요청 content-type/body 크기, 출력 escaping, symlink/path traversal 방어, secret/raw provider error redaction이 필요하다. local server는 production multi-user service가 아니며 0.0.0.0/public publish를 기본 제공하지 않는다. 실제 지원 플랫폼과 browser 검증 범위는 기록한다.

파싱/Drive/LLM 작업은 비동기 job로 보이며 한 번에 한 실행만 진행한다. 생성 전 preview에는 실제 전송 모델·문맥·질문 수×설정 수 최대 요청 건수를 표시한다. 사용자의 실행 클릭이 job를 만들고 idempotency key로 중복 클릭·refresh의 중복 과금을 막는다. 제출 시 config와 snapshot을 고정한다. polling/페이지 reload로 재실행하지 않는다. job 결과는 완료/needs_review/failed/interrupted를 구분하고 모델 dispatch 여부(알 수 없으면 unknown)도 남긴다.

서버 재시작 시 running 상태를 성공으로 바꾸거나 자동 재호출하지 않는다. already-dispatched 요청의 중지는 실제 취소가 확인되지 않으면 ‘취소 완료’라 하지 않는다. 취소 기능을 넣을지와 대기열만 취소할지는 READY에서 결정한다. 출력 저장 실패와 모델 호출 실패를 구분한다. 새 결과는 불변이며 기존 실험 폴더를 덮어쓰지 않는다.

## 비교와 해석

청크 size, top-k, 실제 근거 문자 예산, 모델 토큰 window를 별도 설명한다. 문자 예산은 prompt 전체 token 제한이 아니다. 후보 r1~rK와 실제 전송된 문맥을 따로 표시한다. 인용 원문은 P026 코드의 canonical slice/page가 기준이다. 평가기 미연결이면 Faithfulness/Neutral/Contradiction/Correctness를 0점으로 그리지 않고 ‘아직 평가하지 않음’으로 표시한다. GT 없는 질문의 Correctness와 qrels 없는 검색 지표는 N/A다.

동일 snapshot/questions 비교의 config 축 차이를 보여 주고 모델 raw score·검색 score·정답률을 혼동하지 않는다. 표의 실패 행을 숨기지 않는다. 결과를 선택하면 원문→청크→후보→전달→답변의 연결을 따라갈 수 있어야 한다. 모든 복잡한 원시 로그는 기본 접힘으로 둔다.

## 검증 계획

실제 서버 API 통합·등록경로/입력한도/CSRF·XSS sentinel·중복 요청·재시작/실패 보존을 합성 자료와 가짜 model/Drive backend로 시험한다. fake 모드는 production 설정에서 선택할 수 없고 시험 도구가 주입했음을 UI에도 표시한다. production의 실제 코어 호출 경로는 반드시 연결되어야 한다.

실제 브라우저에서 샘플→설정선택→청킹→검색 preview→비교→원문 locate를 관찰한다. desktop와 좁은 화면, Tab/Enter/Space 접근성, empty/error/loading/미지원 표시, 인용 길이/줄바꿈, 새로고침 후 job 이력을 확인한다. live model/API/계정 호출은 이번 UI 검증에 포함하지 않는다. DOM 테스트나 screenshot 파일 존재만으로 실제 화면 검증을 완료했다고 표시하지 않는다. 도구 차단이 있으면 정확한 미검증 부분만 별도 사람 검토로 남기며 이전 run004 확인을 새 UI에 재사용하지 않는다.

설치 wheel에도 static assets가 포함되어 source 없는 cwd에서 serve가 되어야 한다. 검증용 서버만 종료하며 기존 사용자 서버는 유지한다. 지원 기능의 실제 연결/관찰 증거·회귀·학습 안내를 커밋하고 준비 검토에서 정한 기준을 충족할 때만 완료한다.
