# 3. Hybrid RAG

이 폴더 전체를 별도 위치로 복사하고 설치된 `rag-lab`을 사용합니다. 앞 단계 Python 경로에 의존하지 않습니다. 자료는 가상 문서이며 원본 commit/path/hash는 [stage manifest](stage-manifest.json)에 있습니다.

```sh
rag-lab snapshot --sources sources.json --out .rag-runs/snapshot
rag-lab build --snapshot .rag-runs/snapshot --config bm25.json --out .rag-runs/bm25
rag-lab ask --run .rag-runs/bm25 --config bm25.json --question '생일 휴가 자격은?' --out .rag-runs/answer
rag-lab retrieval-preview --config e5-hybrid.json
```

위 명령은 생성 LLM이나 임베딩 모델을 실행하지 않습니다. e5/bge embedding JSON은 placeholder입니다. 실제 파일/revision/manifest를 준비하지 않은 상태에서 실행하면 명시 오류가 나며 BM25로 대체되지 않습니다.

Dense/Hybrid는 준비된 로컬 HF 설정과 `--execute-retrieval`이 필요합니다. LLM의 `--execute`와 별개입니다. 같은 snapshot에서 `e5-dense.json`, `e5-hybrid.json`, `bge-dense.json`, `bge-hybrid.json`을 선택하고 비교합니다. 먼저 한 번에 검색 방식 하나만 바꾸고, 이후 모델·candidate-k·RRF 상수·문맥 예산을 각각 바꿉니다. 문서 벡터 재사용 중에도 질문 임베딩 계산은 필요합니다.

개발 검증은 수기 벡터와 로컬에서 만든 작은 무작위 SDK 모델로 수행했습니다. 사전학습 모델의 한국어 검색 품질·실메모리·실답변 품질을 검증한 결과가 아닙니다. 평가기는 미연결입니다. P020 고정 후보 리랭커가 추가되었습니다. 설치 소스의 `docs/learning/rag-package/hybrid.md`에 전체 설정·UI·qrels 안내가 있습니다.


## 고정 후보 리랭킹

검색 결과를 고정해 none과 두 CrossEncoder를 비교합니다. 후보 N, 최종 K, 문자 예산을 분리하고 실제 원문·누락을 확인합니다. 실행법과 지표 설명은 [리랭커 학습 가이드](../docs/learning/rag-package/reranking.md)에 있습니다. 이 단계 폴더만 복사할 때는 아래 명령부터 실행하세요.

```sh
rag-lab candidates --build .rag-runs/bm25 --result .rag-runs/answer --question-id q1 --n 20 --out .rag-runs/candidates
rag-lab rerank-compare --candidates-set rerank-candidates.json --variants rerank-variants.json --out .rag-runs/rerank-comparison
rag-lab rerank-report --run .rag-runs/rerank-comparison --out .rag-runs/rerank-report
rag-lab answer-from-rerank --run .rag-runs/rerank-comparison/none/q1 --llm-config llm-local.json --out .rag-runs/answer-preview
```

위 예시에서 none은 완료, 두 모델은 설정 필요 preview입니다. 모델 파일/revision/manifest를 준비하고 `--execute-reranking`을 명시해야 실제 계산합니다. 생성의 `--execute`와 별개이며 가중치를 자동 다운로드하지 않습니다. 전체 후보·본문·원문·순위·실패가 불변 artifact로 남고 보고서 재생은 모델 0호출입니다.
