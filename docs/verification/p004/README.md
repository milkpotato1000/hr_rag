# P004 — 실제 답변·인용·보류 연결 검증

채택 plan: a043f1a3527df9f375b4fe8c0876d9f3417bbb00. 선행 P003: 74b3c35a551671e1387904a0715ea5f8a1625a0c.
현재 제품은 `1. Naive RAG/`의 `scripts/ask.py` 및 재사용 `rag.ask()`다. 사용자 구현 숙제 없이 로컬 모델까지 설치했다.

## 실제 환경과 흐름

- 기존 Ollama 0.40.8·Python 3.12.14·BGE-M3 F16/1024·qdrant-client 1.19.1과 index-v1을 재사용했다.
- 추가 Qwen3:4b는 실제 Q4_K_M·4.0B, digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
- [공식 배포](https://ollama.com/library/qwen3:4b)와 [chat API](https://docs.ollama.com/api/chat)를 확인하고 실제 show/version/tags 및 schema 응답으로 검증했다.
- `generation-lock.json`에 전체 digest·실제 template/parameters/model_info·Apache2.0 license hash·요청 설정을 기록했다. P003 lock/의존성 파일은 보존한다.
- stream=false, think=false, temperature=0, seed=42, num_ctx=8192, num_predict=1024. API 확인은 01-setup-first.txt 마지막 JSON의 actual_probe에 있다. 앞쪽은 실제 다운로드 로그다.
- 단일 검색 → 후보 top-k → 전체 청크 예산 선택 → 단일 /api/chat → JSON/인용 검증. 평가 라벨·rubric·query_id는 제품 경로로 전달하지 않는다.
- 원문 인용을 코드로 검사하고 출처 메타데이터를 corpus에서 보강한다. 의미 정답 여부는 이 검사로 인증하지 않는다.
- content JSON/인용 실패는 사유 있는 보류, provider envelope/HTTP/연결/timeout은 error다. no_context는 생성 미호출이다. 내부 thinking은 저장하지 않는다.

## 검증 파일

| 증거 | 검증 내용 |
| --- | --- |
| rubric.json | 실제 첫 생성 전에 원문에서 작성한 질문별 필수사실/금지오답/출처/복수근거. run.json에 실행 전 hash 기록 |
| 01-setup-first.txt | 실제 다운로드·모델/API 설정 smoke; 실패 없이 완료 |
| 02-first-tests.txt | 기존53 + 초기 P00414 = 67 PASS |
| 03-live-first/ | system-v1 실제14질문 결과·trace·명령. q01 등 실패 원본 보존 |
| first-review.md | Codex 원문 대조 의미 검토와 v2 수정 이유. 사람 검토/자동 키워드 평가 아님 |
| 05-live-v2/ | 동일 모델/질문/문서/K/예산/설정, system-v2로 실제14질문 재검증 |
| final-review.md | 두 번째 실행의 질문별 의미 판정 및 전후 집계 |
| 06-final-tests.txt | 인용 구조와 의미 정답 차이 테스트 추가 후 총68 PASS |
| 04-delivery/ | root19·stage68·단독복사68 및 실제 답변/보류 CLI·역사 증거/원본 보존 |
| 07-contract-and-queue.txt | 최종 계약/큐/index guard·Git 제외 확인 |
| 00-log-format-correction.txt | 초기 STATE 로그 형식 검사 실패와 형식 수정; C4 모델 실패 로그 유지 |

## 재현

먼저 stage에서 `scripts/runtime.py start`로 소유가 확인된 loopback 서비스를 실행한다.
기존 경로에 덮어쓰지 않고 새 증거 경로를 지정한다.

```sh
'1. Naive RAG/.venv/bin/python' docs/verification/p004/run_live.py --output-dir /tmp/p004-live-new
'1. Naive RAG/.venv/bin/python' -m unittest discover -s '1. Naive RAG/tests' -v
python3 -m unittest discover -s tests -v
python3 scripts/contract_guard.py check
python3 scripts/work_queue.py --owner all
```

verify_delivery.py는 이미 존재하는 04-delivery 경로에는 다시 쓰지 않는다. 재검증 시 새 경로로 복사/변경하여 별도 기록한다.
단독 복사는 runtime/venv 없이 제품 소스·데이터·lock·프롬프트를 복사하고 닫힌 색인을 복사해 연다.
이미 승인·설치한 같은 Python 의존성과 loopback 모델 서비스를 공유하며 다른 단계/루트 제품 코드는 import하지 않는다.

## 한계

14개 작은 합성 질문의 단일 실행이며 일반 HR 정확도/성능을 뜻하지 않는다. 전후 개선은 같은 실패를 본 뒤 수정한 것이므로 독립 holdout이 아니다.
구조 검증 통과가 의미 지지를 증명하지 않는다. 실제 조건 누락·과도 보류가 남으면 그대로 기록한다.
HTTP timeout은 호출별 제한이며 전체 deadline이 아니다. 긴 질문·문맥은 토큰 제한을 따로 고려해야 한다.
시간은 모델 교체/로드와 warm 상태가 섞인 단일 관측이다. 모델 로드·embedding/search·generation·total을 trace에서 분리한다.
P005가 이 코어와 실패 사례를 한국어 화면·학습 가이드로 연결한다. P004 완료는 UI 완료를 뜻하지 않는다.
