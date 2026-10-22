# 1. Naive RAG

RAG 방식별 큰 구현 단계다. 현재는 P001 검색 평가 기반, P002 BM25, P003 실제 로컬 Dense 검색과 P004 답변·인용·보류를 구현했다. 평가·BM25는 Python 3.9 이상과 표준 라이브러리만 필요하고, Dense는 아래 격리 런타임을 사용한다.

## 가져온 것과 보존

P001 커밋 `4225bb1d6b9bd017a06e81125c4fce9ed1d7f227`의 평가기·회귀 테스트·합성 데이터 네 파일을 최초 원본 바이트 그대로 확보했다.
앞선 세부 단계 해석으로 작성한 `1. 검색 평가 기반/`을 이 폴더로 옮겼고 기존 README·manifest는 루트 P002 검증 기록에도 보존했다.
`stage-manifest.json`의 source_path는 저장소 기준, destination_path는 이 폴더 기준이다.
`copied_sha256`은 최초 복사 원본 hash이며 이후 현재 코드 hash라고 표시하지 않는다. P002·P003에서도 가져온 여섯 파일을 수정하지 않았다.

같은 큰 단계에 `scripts/run_bm25_baseline.py`와 `tests/test_bm25_baseline.py`를 추가했다.
검색은 질문 본문과 문서 제목·본문만 사용한다. 관련성 정답과 answerability는 기존 평가기에만 전달한다.
데이터·평가기·기존 회귀를 그대로 재사용하며 모델·외부 서비스·패키지는 가져오지 않았다.

## 실행

저장소 루트에서 시작한다면 먼저 이동한다. 이 폴더 하나를 별도 위치로 복사해 실행할 수도 있다.

```sh
cd '1. Naive RAG'
python3 -m unittest discover -s tests -v
python3 scripts/run_bm25_baseline.py \
  --chunks data/synthetic/chunks.jsonl \
  --queries data/synthetic/queries.jsonl \
  --top-k 20 --k 5 10 20 \
  --output-dir /tmp/hr-rag-bm25-new
```

출력 부모 폴더는 존재해야 하고 결과 경로는 파일·폴더·링크 어느 형태로도 존재하면 안 된다.
같은 경로로 재실행하면 실패하므로 새 경로를 사용한다. top-k 기본값은 20, K 기본값은 5 10 20이다.
양의 고유 정수 K와 top-k >= max(K)가 필요하다.

완료된 임시 결과를 준비한 다음 새 최종 폴더를 독점 생성해 네 파일을 게시한다.
전체 디렉터리의 원자적 교체를 보장하는 방식은 아니므로 실행 종료 코드 0을 확인한 뒤 결과를 읽는다.
실패하면 이번 실행이 만든 결과와 임시 파일을 정리하고 기존 사용자 파일을 보존한다.
인자·입력·출력·평가 오류는 stderr와 종료 코드 2로 알린다.

| 결과 | 내용 |
| --- | --- |
| rankings.jsonl | query_id 오름차순의 query_id·chunk_ids. 빈 결과도 질문 행 유지 |
| scores.jsonl | 같은 질문·순위의 query_tokens와 results(chunk_id·score) |
| metrics.json | P001 평가기 결과. SHA-256·K·버전·분모와 query/macro 지표 |
| run.json | 검색기·토큰화·환경·설정·hash·N/avgdl, 분리한 observations에 색인·질문별 검색 시간(ms) |

토큰화 `unicode-word-v1`은 NFKC → casefold → Unicode `[^\W_]+`이다. 문서 입력은 title + LF + text다.
숫자는 남기고 밑줄·구두점으로 나누며 조사·어간·불용어·동의어 처리는 하지 않는다.
BM25는 k1=1.2, b=0.75, 양수 IDF `ln(1+(N-df+0.5)/(df+0.5))`를 사용한다.
질문의 중복 토큰은 제거하고 토큰 문자열 순으로 합산한다. 양수 점수만 내림차순으로 반환하며 정확한 동점은 chunk_id 오름차순이다.
문서가 모두 빈 토큰이거나 질문이 빈 토큰/OOV이면 빈 결과다. 같은 입력·환경의 순위·점수·지표는 재현되며 관측 시간은 별도다.

`휴가`와 `휴가는`은 다른 토큰이다. 작은 합성 corpus 지표는 일반 한국어 검색 품질이나 답변 정확도가 아니다.
근거 없는 질문의 검색/빈 결과 비율은 보류 정확도가 아니다. 실행 시간은 단일 관측으로 엔진 간 우열을 의미하지 않는다.
[합성 데이터 스키마와 정답](data/synthetic/README.md)의 수기 example_rankings는 실제 BM25 결과와 구분한다.

P001 평가기를 별도로 실행하려면 아래처럼 BM25가 생성한 순위를 입력한다.

```sh
python3 scripts/evaluate_retrieval.py --chunks data/synthetic/chunks.jsonl --queries data/synthetic/queries.jsonl --rankings /tmp/hr-rag-bm25-new/rankings.jsonl --k 5 10 20 --output /tmp/hr-rag-bm25-reevaluated.json
```

Git 하네스·기획·완료 상태·실제 결과와 검증 기록은 원래 저장소 루트의 docs/verification/p002/에서 관리한다.
후속 큰 RAG 단계는 별도 기획 때 확정하며 해당 폴더를 미리 만들지 않는다.

## P003: 실제 로컬 Dense 검색

문서 제목·본문을 BGE-M3로 벡터화해 Qdrant local cosine 색인에 저장하고 질문 원문도 같은 모델로 벡터화해 검색한다.
BM25와 같은 corpus·질문·정답·P001 평가기를 사용한다. qrels·answerability는 색인·검색에 넣지 않는다.
Qdrant는 프로세스 안의 로컬 영속 저장소이며 별도 Qdrant 서버나 외부 계정은 필요 없다.

Ollama 0.40.8 공식 macOS tar의 고정 SHA-256을 검증한다. Python 3.12.14·qdrant-client 1.19.1 및 전이 의존성은
`runtime-lock.json`과 `requirements.lock`에 고정했다. 모델은 실제 `bge-m3:567m`, F16, 1024차원이며 전체 digest도 lock에 있다.
macOS arm64와 설치된 uv를 전제로 하며 첫 실행은 공식 런타임·Python·패키지·약 1.2GB 모델을 다운로드한다.

이 폴더에서 실행한다. 이미 만든 색인·결과 경로는 재사용해 덮어쓰지 않으므로 새 경로를 사용한다.

```sh
python3 scripts/setup_runtime.py
.venv/bin/python scripts/runtime.py start
.venv/bin/python scripts/build_dense_index.py --chunks data/synthetic/chunks.jsonl --index-dir .runtime/index-v2
.venv/bin/python scripts/run_dense_baseline.py --chunks data/synthetic/chunks.jsonl --queries data/synthetic/queries.jsonl --index-dir .runtime/index-v2 --top-k 20 --k 5 10 20 --output-dir /tmp/hr-rag-dense-new
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/runtime.py status
.venv/bin/python scripts/runtime.py stop
```

준비가 끝난 현재 환경에는 `.runtime/index-v1`이 있다. 검색할 때 `--index-dir .runtime/index-v1`로 재open할 수 있다.
setup은 lock이 일치하는 설치·모델을 재사용한다. 위 start도 자체 서비스가 이미 실행 중이면 재사용한다.
runtime start/status/stop은 PID·실행 경로·프로세스 시작 시각·127.0.0.1:11434 소유를 검사한다.
다른 서비스가 포트를 사용하거나 PID 소유가 바뀌면 강제 종료하지 않고 오류를 알린다. 서비스 자동 등록·클라우드 로그인은 하지 않는다.
검증 종료 시 자체 서비스는 정지했다.

모델·실행 파일·Python 다운로드·캐시·PID·로그·색인은 `.runtime/`, Python 패키지는 `.venv/`에 있으며 Git에서 제외한다.
Ollama의 표준 초기화가 만든 로컬 키는 저장소 밖 `~/.ollama/`에 있으며 키 내용은 기록·커밋하지 않는다.
서버는 loopback만 사용하고 클라우드는 비활성화한다. 기존 lock의 모델 digest나 corpus·색인 설정이 바뀌면 새 색인을 요구한다.
색인·출력 생성 실패는 기존 파일을 보존하고 이번 미완성 결과를 성공 결과로 게시하지 않는다.

Dense 결과 네 파일은 BM25와 같은 이름이며 P001 CLI로 직접 재평가할 수 있다.
run.json에는 모델·런타임·환경·index manifest·hash와 분리한 index open 검증/질문 embedding/벡터 검색 시간이 있다.
색인 생성 명령은 문서 embedding과 색인 생성·검증 시간을 별도로 출력한다.
전체 N 후보를 조회해 점수 내림차순·정확한 동점은 ID 순으로 top-k를 고른다. cosine 0·음수도 결과에서 제외하지 않는다.

[Ollama embed API](https://docs.ollama.com/api/embed)의 `truncate=false`를 사용하고 응답 개수·차원·유한 값·0벡터를 검증한다.
[Qdrant local mode](https://github.com/qdrant/qdrant-client#local-mode)를 사용하며, 실제 모델은 [BGE-M3](https://ollama.com/library/bge-m3:567m)다.
알 수 없는 payload·중복 point·stale manifest·HTTP/JSON/timeout·출력 실패는 테스트하며 mock을 live 검증으로 부르지 않는다.

## 이번 단계에서 이해하고 실험할 것

구현·오류 수정·회귀 실행은 Codex가 맡고, 사용자는 먼저 결과를 예상한 뒤 근거를 대조한다.
문서를 검색하는 데 성공한 것과 답변을 생성·검증한 것은 다른 단계다. P004에서 답변·인용·보류를 연결했으며, 화면은 P005 계약으로 이어진다.

1. q03에서 자격·기간·신청의 세 근거를 먼저 예상한다. BM25는 birthday-eligibility를 6위, Dense는 2위에 뒀다. Recall@5가 왜 다른지 직접 청크를 읽어 본다.
2. q10의 `재택근무일과`와 문서의 `재택근무는`을 비교한다. BM25는 welfare-meal만 찾았고 Dense는 remote-days도 찾았다. 단어 일치와 의미 검색의 역할 차이를 확인한다.
3. q13 퇴직금 질문은 corpus에 정답이 없다. BM25는 빈 결과지만 Dense는 연차·복지 문서를 반환한다. 가장 가까운 문서라는 이유로 답을 만들어도 되는지 판단해 본다.

이번 작은 평가에서 Recall@5는 Dense=1.0, BM25=0.8939다. 근거 없음 3질문에도 Dense는 모두 결과를 반환했다.
이 숫자는 일반 검색 품질이나 답변 정확도·보류 정확도가 아니다. Dense와 BM25의 원점수 크기도 직접 비교하지 않는다.

실험은 한 변수씩 고정 질문 묶음으로 한다. 첫 요청 예시는 “같은 순위·정답으로 K=1/3/5/10을 평가하고 필요한 근거가 언제 다 들어오는지 보여줘”다.
corpus·질문·모델 digest는 그대로 두고 Recall/MRR/nDCG와 실제 누락 사례를 먼저 본다.
이후 별도 계약에서 표현 변형·새 질문 묶음, 청크 구성, 문맥량, 답변 프롬프트·보류·인용, cold/warm 지연 순으로 넓힌다.
이미 높은 14질문 점수에만 맞춰 설정을 조정하지 않는다. 데이터 변경과 Hybrid·reranker·Agentic은 후속 계획으로 분리한다.

## P004: 질문 → 답변·원문 인용·보류

`rag.ask()`가 검색 한 번 → 전체 청크 문맥 선택 → 생성 한 번 → 인용 검증을 수행한다.
기본 Dense를 BM25로 바꿔 비교할 수 있다. query_id·answerability·relevance·평가 rubric은 운영 경로에 전달하지 않는다.

```sh
.venv/bin/python scripts/setup_generation.py
.venv/bin/python scripts/ask.py --question "생일 휴가는 누구나 입사 직후부터 사용할 수 있나요?"
.venv/bin/python scripts/ask.py --question "퇴직금 계산식은 어떻게 되나요?" --retriever bm25
.venv/bin/python scripts/runtime.py stop
```

P003 환경과 `.runtime/index-v1`을 이미 준비했다. 재시작은 `scripts/runtime.py start`로 한다.
처음 다른 위치에서 재현하려면 앞 절의 setup_runtime·build_dense_index와 위 setup_generation 순으로 준비한다.
추가 생성 모델은 약 2.5GB `qwen3:4b` Q4_K_M이다. 실제 digest·양자화·template·parameters·라이선스 hash는
`generation-lock.json`에 별도 고정했다. 기존 `runtime-lock.json`과 임베딩 색인은 변경하지 않는다.
[공식 chat API](https://docs.ollama.com/api/chat)의 stream=false·think=false·JSON schema와
 temperature=0·seed=42·num_ctx=8192·num_predict=1024를 실제 모델로 검증했다. 고정 seed가 바이트 재현성을 보장하지는 않는다.

CLI 기본값: `--retriever dense --top-k 5 --index-dir .runtime/index-v1 --max-context-chars 8000 --timeout-seconds 120`.
stdout은 결과 JSON 하나, 실행 오류는 status=error 및 exit2, 진단은 stderr다. timeout은 각 HTTP 요청의 제한이며 전체 파이프라인 deadline은 아니다.
정상 답변과 보류는 exit0이다. 응답 JSON의 trace에서 원래 후보·점수·원문, 실제 전달 문맥, 제외 사유,
prompt 버전/hash·실제 messages, corpus/index manifest hash·모델 digest·요청 설정·구간별 시간을 확인한다.
Dense의 index hash는 검증한 manifest hash이며 저장소 파일 전체의 byte hash가 아니다.

문맥 예산은 JSON으로 직렬화한 각 청크 객체의 Unicode 문자 수 합계다. ID·본문·출처 등 메타데이터도 포함한다.
전체 프롬프트의 토큰 제한은 아니다. top-k 순서대로 청크 전체가 남은 예산에 들어가면 선택하고 초과하면 건너뛴다.
문장 중간에서 자르지 않으므로 “수습 제외” 같은 조건을 잘라 잃지 않는다. 예산이 너무 작으면 no_context로 생성 호출을 생략한다.
현재 합성 문서는 작지만 임의의 큰 질문은 모델 context 한계에 영향을 줄 수 있다.

- answered: 인용이 하나 이상이고, 모든 인용 ID가 실제 전달한 문맥에 있으며 quote가 그 청크 text의 정확한 부분문자열이다.
- abstained / model_abstained: 모델이 보류했다. 최종 문구는 인사 담당자 확인을 안내하며 최종 인용은 비운다.
- abstained / invalid_model_response: 모델 content의 JSON·상태·본문·인용 검증에 실패했다. 원응답과 사유를 trace에 남긴다.
- abstained / no_context: 전달 가능한 문맥이 없어 LLM을 호출하지 않았다.
- error / input·provider·timeout·execution: 입력·HTTP/연결·timeout·색인/lock 등의 실행 오류. 문서에 근거가 없다는 뜻이 아니다.

인용의 source·title·version·document_id는 모델이 만든 값 대신 corpus에서 보강한다. 모델이 이 필드를 조작해 보내면 검증에 실패한다.
인용 구조 검증은 문장이 답변을 의미상 지지하는지 자동으로 증명하지 않는다. 의미 검토는 별도 rubric과 원문을 읽어 수행한다.
내부 thinking 전문은 수집하지 않는다. 재검색·답변 수리 생성·무한 재시도는 없다.

단위 테스트의 fake provider와 실제 모델 검증은 구분한다. 루트 `docs/verification/p004/`에는 실제 생성 전에 작성한 rubric,
실제14질문 출력과 명령·trace·Codex 원문 대조 검토·회귀·단독 복사 증거를 보관한다. 사용자나 사람이 검토했다고 표기하지 않는다.

현재 system-v2 실제14질문 원문 대조 결과(Codex 검토): 답 가능11개 중 정확5/부분2/과도보류4, 근거 없음3개 적정보류3.
q01/08/09 과도 보류, q03/07 조건 누락, q11 잘못된 인용 차단 사례가 남아 있다. 프롬프트 개선이 정확도를 높였다고 주장하지 않는다.
