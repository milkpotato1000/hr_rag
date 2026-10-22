# P003 실제 로컬 모델·Dense 검색 검증

2026-10-22 Asia/Seoul, dev의 채택 plan `8fb517ba4f82cadd4b7614f0aabcd4968908f19f`.
제품은 `1. Naive RAG/` 안의 검색 단계까지다. 답변 생성·인용·보류와 화면은 P004/P005의 후속 계약이며 이 작업에서 완료했다고 주장하지 않는다.

## 실제 실행 환경과 출처

- 공식 Ollama 0.40.8 macOS tar의 SHA-256 `29fce20c736f62aa8885b1e83552c5fd8dcc63edc5ffc1b47f2de591a06cde44` 검증 후 프로젝트 `.runtime/ollama`에 설치했다.
- `.runtime/python`의 Python 3.12.14, `.venv`의 qdrant-client 1.19.1을 포함한 20개 패키지를 사용한다. [requirements.lock](<../../../1. Naive RAG/requirements.lock>)과 [runtime-lock.json](<../../../1. Naive RAG/runtime-lock.json>)에 실제 버전·파일 hash를 기록했다.
- 실제 BGE-M3:567m은 F16, 1024차원이다. 전체 digest는 `7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab`. 모델 정보·MIT 라이선스와 텍스트 hash도 lock에 있다.
- 공식 근거: [Ollama release](https://github.com/ollama/ollama/releases/tag/v0.40.8), [embed API](https://docs.ollama.com/api/embed), [BGE-M3](https://ollama.com/library/bge-m3:567m), [원 모델](https://huggingface.co/BAAI/bge-m3), [Qdrant client](https://github.com/qdrant/qdrant-client).

모델·archive·실행 파일·Python 다운로드·캐시·PID·로그·Qdrant 데이터는 `.runtime/`, 의존성은 `.venv/`에 두고 Git에서 제외했다.
Ollama 표준 초기화의 로컬 키는 저장소 밖 `~/.ollama/`에 있으며 키 내용은 출력·커밋하지 않았다.
클라우드 로그인·유료 API·전역 패키지·서비스 자동 등록·배포는 사용하지 않았다. OLLAMA_NO_CLOUD를 켜고 127.0.0.1:11434만 사용했다.
최종 실제 stop/status에서 서비스 정지를 확인했다.

## 실패 → 수정 → 재검증

1. [첫 setup](01-setup-first.txt)은 HTTP readiness timeout으로 실패했다. listen 직후 HTTP 응답 준비 전 timeout을 즉시 실패로 처리했다. 전체 30초 deadline 안에서 일시적 OSError를 재시도하도록 수정했다. [실모델 setup 재검증](02-setup-recheck.txt)이 성공했고 start 재시도 회귀도 추가했다. 진행 표시의 ANSI·줄 끝 공백은 제거한 발췌이며 전체 원본은 `.runtime/setup-recheck-raw.log`에 보존했다.
2. [첫 통합 테스트](04-first-tests.txt)는 53개 중 1개 실패했다. 두 Qdrant 호출의 cosine이 약 1e-16 달랐는데 후보 순서 검증이 exact equal을 요구했다. 독립 고정 순위와 `[1,1,1/sqrt(2),0,-1]`을 계약 허용 오차 1e-6로 검증하도록 수정했다. 검색 산식·corpus·정답·계획 조건은 바꾸지 않았다.
3. [수정 근거](05-corrections.txt)와 [최종 전체 회귀](06-final-tests.txt): **53 PASS**. 실제 부분 색인 게시 실패와 Python patch·전이 의존성 lock 검증도 확인했다.

모델 다운로드나 실행을 mock으로 대체하지 않았다. 알려진 벡터·HTTP 서버·실패 주입은 아래 offline 테스트에만 썼다.

## Offline/로컬 통합 검증과 live 구분

53개는 기존 P001 19개 + P002 18개 + P003 16개 테스트다. HTTP 테스트는 외부 인터넷 없이 loopback 테스트 서버로 실패를 만든다.
Qdrant fixture는 a=[1,0], b=[0,1], c=[1,1]와 query=[1,0]의 [a,c,b] 및 [1,1/sqrt(2),0]을 독립 기대값으로 검증한다.
0·음수 cosine, 정확한 동점, 후보 순서 변경, 별도 프로세스 재open, unknown payload·중복 chunk/point 매핑·stale corpus/model/config를 검사했다.
벡터 개수·차원·bool·NaN/Infinity·0벡터, HTTP 오류·JSON·redirect·timeout, 색인/결과 생성·평가·쓰기/게시 실패에서 기존 파일 보존과 새 미완성 결과 정리를 확인했다.
자체 PID·binary·시작 시각·listener 소유가 다른 경우 start/stop을 거부하는 테스트도 있다.

실제 모델 증거는 별도다.

- [최초 live](03-live/commands.txt): idempotent setup, status, 실제 15문서 embedding·색인 생성·닫기, 새 프로세스에서 재open한 14질문 Dense, 동일 조건 BM25 실행.
- [최종 live 및 회귀 원본](07-live-final/commands.txt): 자체 stop → stopped → start → idempotent start, 전체 53 PASS·루트 P001 19 PASS, 14질문 Dense/BM25 재실행, P001 CLI로 각각 재평가한 JSON 바이트 일치.
- [실제 manifest](07-live-final/index-manifest.json)와 [point/payload 대응](07-live-final/payload-mapping.json): 고정 UUID, 원본의 일곱 payload 필드, corpus SHA·모델 digest·1024차원·Cosine·텍스트 구성·client version·15 points 일치.
- [전달 대조](07-live-final/delivery-checks.json): 여섯 원본 파일과 P001/P002 완료 카드·기존 증거가 그대로다. 큰 단계의 코드·data·lock과 닫힌 색인만 임시 폴더로 복사해 **53 PASS** 및 실제 Dense 순위 일치를 확인했다. 이 검증은 동일한 승인 Python 의존성 interpreter와 loopback Ollama 서비스를 재사용하며 모델 가중치·venv를 복제하지 않았다. 다른 단계/루트 제품 코드 import는 없다.
- 최종 status → stop → stopped를 명령 기록에서 확인할 수 있다. 모델·색인은 로컬에 남고 서비스는 정지했다.

## 동일 조건 비교와 해석

최종 기준: corpus 15청크, 질문 14개 중 answerable=11/unanswerable=3, 같은 top-k=20 및 K=5/10/20, 같은 Python 3.12.14와 P001 평가기다.
[Dense 결과](07-live-final/dense/metrics.json), [BM25 결과](07-live-final/bm25/metrics.json), [비교 JSON](08-comparison.json).
각 폴더의 rankings/scores/run에 순위·원점수·환경·모델·설정·hash와 구분한 시간이 있다. 원점수 크기는 두 방식 간 직접 비교하지 않는다.

| K | Dense Recall | BM25 Recall | Dense MRR | BM25 MRR | Dense nDCG | BM25 nDCG |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 1.000000 | 0.893939 | 1.000000 | 0.803030 | 0.999471 | 0.775828 |
| 10 | 1.000000 | 0.954545 | 1.000000 | 0.803030 | 0.999471 | 0.808825 |
| 20 | 1.000000 | 0.954545 | 1.000000 | 0.803030 | 0.999471 | 0.808825 |

Precision@5는 Dense=0.327273, BM25=0.272727이다. 근거 없는 질문의 결과 있음 비율은 Dense=3/3, BM25=2/3이며 빈 결과는 각각 0/3, 1/3이다.
Dense는 전체 N 후보에서 가까운 문서를 반환하므로 결과 존재는 근거 충분성이나 답변 보류 정확도가 아니다.

[실제 Dense 순위](07-live-final/dense/rankings.jsonl)와 [BM25 순위](07-live-final/bm25/rankings.jsonl)를 보존한 [질문](<../../../1. Naive RAG/data/synthetic/queries.jsonl>)·[문서](<../../../1. Naive RAG/data/synthetic/chunks.jsonl>)에 대조했다.

1. **q03 복수 근거**: 생일 휴가의 자격·기간·신청을 묻는다. birthday-eligibility(입사 3개월 및 수습 제외)는 BM25 6위, Dense 2위다. Dense top 3에 birthday-request·birthday-eligibility·birthday-window가 모두 들어왔다.
2. **q10 주변 근거**: 식대의 직접 근거 welfare-meal은 양쪽 1위다. 근무일 구분의 등급 1 근거 remote-days는 BM25에서 검색되지 않았지만 Dense 2위다. 단순 어절 토큰화와 의미 벡터 검색의 실제 차이다.
3. **q13 근거 없음**: 퇴직금 계산식은 corpus에 없다. BM25는 빈 결과, Dense top 5는 annual-accrual·annual-halfday·welfare-birthday·welfare-meal·birthday-eligibility다. 이들은 연차·복지 규정이며 퇴직금 계산식을 제공하지 않는다. 다음 단계에서 인용·답변/보류 검증이 필요한 이유다.

작은 합성 데이터에서 관측한 차이이며 일반 한국어 품질이나 답변 정확도를 입증하지 않는다. 생성 자체는 아직 구현하지 않았다.
최종 run은 서비스 재시작 후 실행했고 첫 query에는 모델 로드가 섞일 수 있다. 이후 warm 조건과 다르므로 단일 측정 지연으로 엔진 우열을 주장하지 않는다.
문서 embedding·색인 생성 시간은 최초 live build 출력, index open·질문 embedding·벡터 검색 시간은 run.json observations로 구분했다.

## 실행·학습·완료 근거

사용자는 구현보다 질문의 예상 근거·실제 순위·한 변수 실험의 해석에 집중한다. [큰 단계 README](<../../../1. Naive RAG/README.md>)에 실행/정지와 이번 학습 체크를 기록했다.
최종 화면·답변·인용·보류를 포함한 종합 학습 가이드는 후속 P005 계약에서 연결한다.

| 조건 | 최신 근거 |
| --- | --- |
| C1 | runtime-lock/requirements.lock, 01 실패와 02 수정 재검증, 최종 live의 자체 stop/start/status·Git 제외 |
| C2 | 실제 15문서/14질문, index manifest·payload UUID 대응, 별도 프로세스 재open·모델/질문 embedding 검증 |
| C3 | 04 최초 실패·05 수정·06 최종 53 PASS, 독립 cosine·stale/HTTP/벡터/출력 및 소유 경계 검증 |
| C4 | 최종 Dense/BM25 네 파일, P001 재평가 바이트 일치, 비교 JSON·세 실제 사례·관측 한계 |
| C5 | 루트 19 PASS, 큰 단계/단독 복사 53 PASS·실모델 검색, 원본·실패 로그 보존 및 README |
| C6 | [최종 계약·큐·index 검사](09-contract-and-queue.txt), 선행 DONE, 최신 PASS·비어 있지 않은 커밋 대상 근거 |

이미 준비된 런타임·색인을 최종 검증하는 재현 명령(저장소 루트, 새 결과 경로):

```sh
python3 docs/verification/p003/verify_live.py --output-dir /tmp/hr-rag-p003-new-evidence
python3 scripts/contract_guard.py check
python3 scripts/work_queue.py --owner all --json
```

최초 설치·새 색인 생성은 큰 단계 README의 setup/start/build/search/status/stop 순서를 따른다.
