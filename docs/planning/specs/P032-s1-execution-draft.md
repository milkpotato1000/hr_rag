# P032 S1 — 실제 검색·리랭커 검증 실행안

2026-11-28 DRAFT. P031 완료 증거와 설치 출처를 검토한 뒤 확정할 실행안이다. 아직 다운로드·모델 실행을 지시하지 않는다. 전체 P032의 답변·LLM 청킹·사용자 링크 검증 범위를 축소하지 않는다.

## 입력과 실행 순서

- 입력은 P032 설계에 고정한 합성 HR PDF와 승인된 질문 10개다. PDF hash를 확인하고 새 설치물의 파싱 결과를 대조한다. 승인 GT를 고치지 않고 새 canonical에 fact/span과 청크 qrels를 작성·검토한다.
- P031 고정 recipe 네 개만 사용한다. E5-small → mMiniLM reranker → BGE-M3 → BGE reranker 순서로 파일을 준비하며 준비·추론은 동시에 하지 않는다. 공개 원본 파일만 다운로드하고 HF 인증 토큰·사용자 캐시는 사용하지 않는다.
- 먼저 두 질문의 작은 입력으로 tokenizer·모델 로드·출력 차원/점수·원문 대응·worker 종료를 확인한다. 작은 입력은 최대 20개 청크이며 이 결과를 전체 검색 성능으로 표시하지 않는다.
- 이후 동일 규칙 청크에서 BM25/E5 Dense/E5 Hybrid/BGE Dense/BGE Hybrid와 저장 E5 Hybrid 후보의 none/mMiniLM/BGE reranker를 비교한다. 상세 통제 조건은 비교 행렬 문서를 따른다. 후보 재생은 재검색을 포함하지 않는다.
- 작은 모델의 로드/입력/자원 시험이 실패하면 큰 모델로 자동 확대하지 않는다. 원인을 기록하고 필요한 수정은 독립 검증 후 새 실행 ID로 검토한다. 품질 수치가 낮다는 이유로 결과를 삭제하거나 유리한 qrels로 바꾸지 않는다.

## 실행 한도 후보

| 항목 | 후보 한도와 기록 |
| --- | --- |
| 파일 준비 | 고정 원본 총 5,572,099,173bytes, 모델당 다운로드 작업 1개·상위 자동 재시도 0. HF 내부 HTTP 요청/재시도와 논리 작업 수는 구분 |
| 디스크 | 시작 시 최소 14,511,255,971bytes 여유와 P031 작업별 검사 모두 만족. 원본·export·실패 기록 보존, 다른 캐시 삭제 금지 |
| 다운로드/변환 | 다운로드 작업당 900초, BGE 변환 300초. P031의 파일 개수·크기·tensor-only 변환·4GiB RSS 한도 유지 |
| 검색 모델 | CPU float32, batch1, 입력 512토큰 이하. 실제 tokenizer에서 초과하면 실패하며 조용히 자르지 않음 |
| 추론 작업 | worker당 최대 300초. 준비가 아닌 모델 추론도 동시 worker 1개. 전체 S1 실제 준비/추론 시작부터 2시간 경과 시 새 작업 금지 및 실행 중 owned worker 회수 |
| 추론 수 | smoke embedding 최대 6worker, 본 검색 최대 42worker(문서2·질의40). reranker smoke 최대4worker/80pairs, 본 비교20worker/400pairs. 합계 추론72worker 이내. 동일 artifact 재사용 시 실제 수는 감소 |
| 모델 호출 제외 | 생성·LLM 청킹·평가기·NLI·Ollama 제어·유료 API·Drive/OAuth 호출 0. 기존 P013 grant 사용 0 |

위 한도는 성공 보장이 아니라 실행 범위다. 2시간 안에 모든 작업을 마치지 못하면 완료된 셀과 미실행 셀을 그대로 보고하며 시간을 자동 연장하지 않는다. 실패 후 다음 실행의 한도를 자동 초기화하지 않는다. 첫 요청 전에 원본 identity·실제 작업 수·설정·예산을 manifest로 고정하고 dispatch 직전에 누적 카운터를 저장한다.

## 추론 중 자원 관찰과 회수

현재 embedding.encode와 reranker.score는 communicate timeout 및 종료 시 worker RSS를 제공하지만 실행 중 OS pressure를 관찰하지 않는다. 준비용 model_process의 monitor가 자동 적용된다고 보지 않는다. P032 S1 구현 범위에는 기존 추론 경로의 감시·중단·회수 보완을 포함한다.

- 시작 전 macOS pressure가 normal이어야 한다. 실행 중 목표 간격 250ms로 pressure와 직접 생성한 worker RSS를 관찰하고 실제 관찰 시각·최대 간격·측정 방식도 남긴다. 계측 명령 자체의 지연도 timeout에 포함한다.
- warning/critical, RSS 4GiB 이상, 계측 불가, 작업/전체 deadline 또는 사용자 취소 시 현재 owned worker만 종료하고 wait로 회수한다. OS 전체의 OOM을 방지한다고 보장하지 않으며 250ms 사이 peak를 측정한 것으로 표시하지 않는다.
- 모델 프로세스를 직접 소유한 경로에서 감시한다. 외부 래퍼만 종료하여 자식이 남는 구조나 프로세스 이름으로 모든 Python/Ollama를 종료하는 방식은 사용하지 않는다. 자식 생성이 생기면 별도 소유권/회수 검증 없이는 실행하지 않는다.
- stdin 전달과 stdout/stderr 소비가 감시를 막거나 pipe 교착을 일으키지 않도록 구현한다. 정상·오류·timeout·KeyboardInterrupt/SystemExit에서도 동일한 소유 worker의 종료 확인을 남긴다. 특히 현재 reranker의 timeout 외 예외 경로도 검증한다.
- 미완료 작업의 출력은 성공 artifact로 공개하지 않는다. dispatch 전후, 시도/완료 수, 마지막 관찰, 회수 결과와 재개 가능 여부를 별도 기록한다. 종료를 확인하지 못하면 후속 실행을 중지한다.
- P013 runner·서버 제어·기존 grant를 가져오지 않는다. macOS에서 실제 관찰한 결과를 Linux/MPS/다른 컴퓨터의 성공으로 확대하지 않는다.

## 실행 전 독립 검증과 완료 증거

1. 작은 dummy owned worker로 정상 종료, timeout, pressure 변경, RSS 한도, 계측 실패, 취소, 출력이 많은 경우를 검증한다. 테스트가 외부 사용자 프로세스를 건드리지 않는지 확인한다. 성공 후 실제 tiny SDK의 기존 결과·설치 회귀를 대조한다.
2. 최종 설치 artifact/SDK/profile/source identity를 고정하고 원본 span과 qrels를 읽기 검토한다. 새 tokenizer의 입력 길이 사전 검증과 후보 저장·재생을 확인한다.
3. 실제 공개 가중치 준비·로드와 검색/리랭킹 결과를 별도로 기록한다. 다운로드 fixture, random tiny 모델, 실제 사전학습 모델 결과를 혼합하지 않는다.
4. 질문별 순위·원문·Recall@K/MRR/nDCG·candidate/top-K/context fact 회수·cold 시간/RSS·실패를 비교한다. gt09/10의 required-fact 없음은 N/A다. 생성 답변의 정확성은 이 단계에서 판정하지 않는다.
5. 최종 결과와 재현 명령을 CLI/UI 학습 자료에 연결한다. S1 완료로 P032 C2/C3 전체를 체크하지 않으며 생성 profile/사용자 링크에 의존하는 범위를 계속 남긴다.

P031 최종 설치/UI 증거, 감시 구현 범위의 준비 검토, 위 한도와 작업 수 재계산이 완료된 후 정확 READY를 만든다. 현재는 계획만 저장하며 실행 요청은 0이다.
