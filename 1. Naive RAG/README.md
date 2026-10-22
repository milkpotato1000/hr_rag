# 1. Naive RAG

RAG 방식별 큰 구현 단계다. 현재는 P001 검색 평가 기반과 P002 BM25 검색 기준선만 구현했다.
Dense 검색·생성 모델·최종 답변 기능은 후속 P카드 범위다. Python 3.9 이상과 표준 라이브러리만 필요하다.

## 가져온 것과 보존

P001 커밋 `4225bb1d6b9bd017a06e81125c4fce9ed1d7f227`의 평가기·회귀 테스트·합성 데이터 네 파일을 최초 원본 바이트 그대로 확보했다.
앞선 세부 단계 해석으로 작성한 `1. 검색 평가 기반/`을 이 폴더로 옮겼고 기존 README·manifest는 루트 P002 검증 기록에도 보존했다.
`stage-manifest.json`의 source_path는 저장소 기준, destination_path는 이 폴더 기준이다.
`copied_sha256`은 최초 복사 원본 hash이며 이후 현재 코드 hash라고 표시하지 않는다. 이번 P002에서는 가져온 여섯 파일도 수정하지 않았다.

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
