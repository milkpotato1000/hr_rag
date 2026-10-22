# P005 — 학습 UI/API와 Naive RAG E2E 인계

채택 plan: 863a574b26535f80418b54e2f3204024e6e97fa8. P004 완료38d276e를 먼저 push하고 실제 코어/스키마를 대조한 뒤 순차 진행했다.
검토는 [00-interface-review.md](00-interface-review.md)에 있다. 제품 폴더는 계속 `1. Naive RAG/` 하나다.

## 제공 기능

- `scripts/serve.py --port 8000`: 127.0.0.1에만 bind. 외부 CDN·계정·호스팅이 없다.
- 한국어 질문/예시, Dense/BM25, top-k, 문맥 예산. 로딩·중복 클릭 방지·실패 후 재시도.
- 검색 후보 순위/점수/원문/출처, 실제 전달/제외 문맥, 답변·원문 인용·보류·실행 오류를 분리 표시.
- 실제 model digest/prompt hash/옵션/구간별 시간, 전체 trace와 JSON 다운로드.
- `rag.ask()`를 그대로 사용하며 별도 프롬프트/검색/인용 검증을 UI에서 구현하지 않는다.
- 서버 내부 pipeline lock으로 Qdrant/model 요청을 직렬화한다. GET 정적 자산은 별도 스레드로 응답한다.
- HTTP 입력400 / provider502 / timeout504 / 기타500 / 정상답변·보류200. 문서 근거 부족과 실행 장애를 혼동하지 않는다.
- 질문·모델·문서 문자열을 textContent로 렌더링하며 raw HTML을 실행하지 않는다.

## 테스트와 실제 실행의 구분

`01-first-tests.txt`: 기존68+HTTP6=74 PASS. HTTP 테스트는 실제 loopback 서버에 고정 fake pipeline을 주입한 오프라인 통합이며 모델 품질 증거가 아니다.
실제 모델 재시작 검증에서 metadata 행 순서 오탐을 발견해 회귀2개를 추가했다.
`03-delivery-final/commands.json`: 최종 stage76·root19·단독 복사76 PASS.
같은 디렉터리의 q10-live-http/q13-live-http는 소스·웹·데이터·가이드·프롬프트·색인을 따로 복사한 서버에서 실행한 **실제 BGE/Qdrant/Qwen HTTP E2E**다.
승인된 같은 Python 의존성과 loopback 모델 서비스는 공유한다. 다른 단계나 루트의 제품 코드는 가져오지 않는다.
`preservation.json`은 기존P001~P004 카드/증거·원본6개 hash·모델lock·P004 rag/ask/prompt 보존을 확인한다.

## 브라우저에서 확인한 흐름

Cua로 실제 Codex in-app browser의 http://127.0.0.1:8000 을 열고 버튼/입력/설정을 조작했다. API 결과만으로 화면 확인을 대신하지 않았다.

| 관찰 | 실제 결과와 증거 |
| --- | --- |
| 초기 화면 | browser/01-home.jpg. 가상 자료 표시·질문·설정·학습 안내 |
| q10 정상 | live/q10-browser-download.json을 UI의 결과 JSON 저장 버튼으로 실제 다운로드. browser/02-answer.jpg에 답변/인용/검색원문/전달문맥 |
| q13 근거 없음 | live/q13-browser-observation.json. 실제 모델보류·생성1회·5개 무관 후보. browser/03-mobile-abstain.jpg |
| 390px 좁은 화면 | width390/scrollWidth390을 DOM으로 확인. 세로 스크롤, 긴청크·출처·digest 줄바꿈, 한 열 답변/검색 구성 확인 |
| 모델 정지 오류 | owned-stop-for-error-check.json → error-before.json: 실제 연결 실패를 provider 오류로 표시. 보류로 숨기지 않음. 재시도 버튼 활성 |
| 상태 표시 수정 | error-after.json / browser/05-error-after.jpg: 모델 정지와 미관측 시간 —. 재시작 후 페이지 reload 없이 실행 중 표시로 갱신 |
| q03 복수 근거 | live/q03-browser-observation.json. 실제3개 인용과 원문. browser/06-desktop-multiple-evidence.jpg 및 08-answer-and-evidence.jpg |
| 1200px 화면 | width1200/scrollWidth1200. 답변·검색 두 열, 문맥/trace 아래 배치. 실제 console error/warn 조회는 [] |
| 문맥 예산1 | live/no-context-browser.json. BM25 후보1개는 있지만237자 청크가 제외돼 no_context·생성0회 |
| HTML 문자열 | live/html-text-browser.json. 질문의 img/onerror 문자열은 trace에 문자로 남고 실제 img 노드는0, JS dialog 없음 |

AX/DOM을 확인하고 해당 원문·문맥을 펼쳐 읽었다. screenshot은 실제 브라우저 캡처이며 생성 이미지가 아니다.
브라우저 조작 중 정확 일치 label locator가 하나 실패해 DOM을 확인하고 combobox role로 조작했다. 제품 오류나 모델 실패로 분류하지 않는다.
임시 viewport override는 검증 후 해제하고 사용자용 탭은 유지한다.

## 발견한 실패와 수정

1. 모델 정지 후 상단 runtime 상태가 초기 “실행 중”으로 남았다. `error-before.json`과 `04-error-before.jpg`를 보존했다.
   app.js에서 요청 전후 상태를 새로 읽고 미관측 세부시간은0 대신 —로 표시한다. 실제 정지/재시작/재시도로 확인했다.
2. Ollama 재시작 후 /api/show의 parameters 행 순서가 달라졌다. 값·digest는 같아도 P004 문자열 비교가 모델 변경으로 오판했다.
   `live/retry-metadata-failure.json`, `02-delivery/failure.txt`, 첫 standalone502 서버 로그를 보존했다.
   `generation.py`/`setup_generation.py`의 비교에서만 (name,value) 쌍을 정렬한다. lock 원문·모델·옵션은 변경하지 않았다.
   중복 stop 항목도 유지하므로 값/개수/digest/template 변경은 계속 거부한다. 회귀2개와 실제 setup 재사용·q03·단독 HTTP로 재검증했다.
   수정 diff는 adapter-order-fix.diff, dev 피드백은 docs/feedback/dev/P005-runtime-metadata.md다.

이 수정은 P004의 계약/기존 증거를 바꾼 것이 아니라 P005 실제 재시작에서 드러난 어댑터 결함을 보수한 것이다.

## 학습과 한계

`LEARNING_GUIDE.md`는 원문→검색→문맥→생성→인용·보류, 첫3질문, 실패 계층, Recall/MRR/nDCG와 의미평가,
과도보류/허구답변, top-k·검색방식·문맥·프롬프트 실험, 테스트 층, cold/warm 시간, Codex 요청 예시를 실제 파일/명령과 연결한다.
`04-k-experiment/`는 q03에서 top-k만1/3/5/10으로 바꾼 실제 HTTP 학습 예다. 표와 의미 해석은 k-experiment-review.md에 있다.
P004의 고정14질문 품질은 정확5/부분2/과도보류4 및 근거없음3개 적정보류3이었다. UI 연결과 테스트 통과가 이 품질 한계를 없애지 않는다.
일부 실제 답변의 연1일·직무제외·승인주체 누락, 과도 보류, 인용 오류를 그대로 공개한다. Codex 원문 대조이며 사람이 검토했다고 주장하지 않는다.
단일 관측·작은 합성 세트이며 holdout이나 보편 HR 정확도/지연을 의미하지 않는다. 실제 회사의 인사 규정으로 적용하지 않는다.

## 실행/종료

제품 폴더에서 `.venv/bin/python scripts/runtime.py start` 후 `.venv/bin/python scripts/serve.py --port 8000`.
브라우저 http://127.0.0.1:8000. 현재 환경의 모델·색인은 이미 설치/준비했다. 사용자에게 구현·다운로드·테스트 작성을 숙제로 넘기지 않는다.
UI 터미널 Ctrl+C → `.venv/bin/python scripts/runtime.py stop` 순으로 종료한다. 다른 서비스는 종료하지 않는다.
인계 시 UI와 소유 모델 서비스는 실행 상태로 두고, 정확한 상태는 live/final-runtime-status.json과 final-handoff.txt에 기록한다.
