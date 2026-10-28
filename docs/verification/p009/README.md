# P009 검증: ID 선택 → 요청 원문 조립

2026-10-28. plan `03f0a351747373c622ee4108b6d6083889f509fd`, 채택 merge `81ed9cb`. P006 완료를 선행으로 현재 `1. Naive RAG/`에 적용했다.

모델 출력은 status/answer/citations이며 각 citation에는 chunk_id만 허용한다. 요청별 schema enum을 실제 전달 ID로 구성하고 코드에서 독립 검증한다. 코드가 동일 요청의 불변 snapshot에서 선택 순서대로 전체 text와 메타데이터를 조립한다. 전체 원문과 정확히 같다는 사실은 답변의 의미적 지지를 증명하지 않는다.

## 증거

| 범위 | 증거 | 확인 |
| --- | --- | --- |
| 모델 응답·원문 조립 | `live/*.json`, `07-boundaries-final.txt` | 전체 UTF-8 동일·앞뒤 공백/PDF 줄바꿈·순서·ID 검증 |
| schema 격리 | `03-offline-permitted.txt`, `07-boundaries-final.txt` | 서로 다른 순차/동시 요청의 enum·인용 격리, 실제 API body spy와 trace 일치, shared lock/template 불변 |
| lock 버전 | `generation-lock-before.json`, `generation-lock.diff`, `lock-migration.json` | schema_version2, id_only_v2, static template+dynamic rule; 모델 subtree·sampling 불변 |
| 실제 빈 문맥 probe | `04-setup-probe.json` | 실제 Ollama가 maxItems0 schema로 보류 응답. setup 재사용 후 lock 바이트 불변 |
| 회귀 | `03-offline-permitted.txt`, `06-root-regression.txt`, `08-copy-regression.txt` | 단계107개, 루트19개, 독립 복사본107개 통과 |
| 실제 의미 검토 | `rubric.json`, `final-review.md`, `05-live-run.txt`, `live/` | 사전 기준, 식대+고정14질문+PDF q06 실제16회, 의미/인용 구조 분리 |
| 기존 자료 보존 | `preservation-before.json`, `preservation-and-trace.json`, `verify_evidence.py` | 203개 파일 hash 및 모델/런타임/sampling 보존, 실제 trace 대조 |
| 화면 | `http-status.json`, `server-restart.json`, `browser-meal.json`, `browser-meal.png`, `browser-check.json` | 소유 UI만 재시작, system-v3, 실제 HTTP 답변·전체 청크·trace 표시 |
| 독립 실행 | `copy-location.json`, `copy-meal.json`, `copy-pdf-q06.json`, `copy-q13.json` | 부모 저장소 없는 단계 복사본에서 CLI 실행; 기존 설치 interpreter/loopback 모델 재사용 |
| 최종 하네스 | `final-checks.txt` | 정확 plan 채택·선행·계약·큐·pre-commit |

## 실패와 재검증

`01-offline-first.txt`, `02-offline-expanded.txt`의 각각 11개 오류는 샌드박스가 loopback 서버 bind를 거부한 환경 오류다. 입력 기대값을 바꾸지 않고 허용된 로컬 실행에서 107개를 통과했다. `guard-first.txt`는 진행 중 P카드 실행 로그 누락을 거부했다. 실행 로그를 추가한 뒤 재검증했다. 기존 실패 기록은 삭제하지 않았다.

실제 모델의 q03/q07/q09 부분 답변과 q08 과도보류도 `live/`와 의미 검토에 그대로 남겼다. 목표 식대와 PDF q06은 최초 P009 실행에서 answered였다. 이전 보고 오류를 매번 재현한다고 주장하지 않는다.

## 실행과 인계

현재 서버는 `http://127.0.0.1:8000/`에서 dev의 새 코드를 사용한다. 작업 디렉터리는 `hr_rag/hr_rag_dev/1. Naive RAG`이며 UI 기본 corpus는 수작성15청크다. source-v2 20청크는 CLI의 명시 경로로 검증했고 기본 UI corpus를 바꾸지 않았다.

재시작: 단계 폴더에서 `.venv/bin/python scripts/runtime.py start` 후 `.venv/bin/python scripts/serve.py --port 8000`. 기존 UI를 중복 실행하지 말고 그 UI의 터미널에서 Ctrl+C로 종료한다. 다른 프로세스를 일괄 종료하지 않는다. 모델 종료는 `.venv/bin/python scripts/runtime.py stop`이다.

독립 복사 실행은 코드·데이터의 위치 독립성을 검증한다. 새 컴퓨터의 인터넷 설치나 모델 다운로드를 재실행한 증거는 아니다. 복사한 색인은 원 실행 종료 후 닫힌 상태로 복사했다. 이전 모델과 설정을 그대로 사용했으며 새로운 모델/재검색/추가 생성/근거 자동 의미 판정은 도입하지 않았다.

학습은 모델의 근거 선택과 코드의 원문 조립을 구분하고, 원문에 있는 조건을 answer가 빠뜨리는지 별도로 평가한다. 변경된 README/LEARNING_GUIDE와 원문 경로 안내가 이를 설명한다.
