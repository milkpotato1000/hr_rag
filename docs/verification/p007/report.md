# P007 청킹·검색 실험 결과

고정 source-v4 23쪽 규정집으로 다섯 방법·14설정을 모두 실행했다. tuning26개(평가 가능23, 문서 범위 밖3), holdout12개(평가 가능10, 범위 밖2)다. 전체 품질 ranking776개, 지연2회 반복1552회를 사용했다. 실패 실험과 진단·UI 검색도 누적 ledger에 포함한다.

## 선정과 주요 비교

후속 후보는 **structure-0(제목/섹션 기반, overlap0)**이다. Dense tuning fact recall@5 → 중복 문자비 → 청크 구축시간 → ID의 사전 고정 규칙으로 선정했다. 후보를 저장하고 hash를 고정한 다음 holdout을 실행했으며 holdout으로 재선정하지 않았다.

| 설정 | 청크 | 중복비 | BM25@5 | Dense@5 | Dense800자 | 구축초 | Dense검색ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| fixed-200-0 | 193 | 1.000 | 0.5362 | 0.6957 | 0.6377 | 0.305 | 2.961 |
| fixed-200-40 | 241 | 1.249 | 0.5362 | 0.7826 | 0.7174 | 0.030 | 3.288 |
| fixed-400-0 | 97 | 1.000 | 0.7899 | 0.8551 | 0.7464 | 0.024 | 1.983 |
| fixed-400-80 | 121 | 1.249 | 0.7754 | 0.9855 | 0.8188 | 0.028 | 1.953 |
| fixed-800-0 | 49 | 1.000 | 0.7826 | 0.8696 | 0.5217 | 0.019 | 1.373 |
| fixed-800-160 | 61 | 1.249 | 0.8478 | 1.0000 | 0.6884 | 0.026 | 1.265 |
| recursive-0 | 117 | 1.000 | 0.7681 | 1.0000 | 0.7464 | 0.082 | 2.302 |
| recursive-80 | 117 | 1.236 | 0.8261 | 0.9638 | 0.7681 | 0.061 | 2.612 |
| structure-0 | 155 | 1.000 | 0.8406 | 1.0000 | 0.9493 | 0.044 | 2.399 |
| structure-80 | 155 | 1.285 | 0.8261 | 1.0000 | 0.8406 | 0.046 | 2.977 |
| semantic-0 | 278 | 1.000 | 0.5870 | 0.7464 | 0.8043 | 29.235 | 3.784 |
| semantic-80 | 278 | 1.574 | 0.6232 | 0.8333 | 0.7681 | 0.040 | 3.926 |
| llm-0 | 621 | 1.000 | 0.2174 | 0.3696 | 0.6884 | 541.722 | 8.139 |
| llm-80 | 621 | 1.949 | 0.5797 | 0.8406 | 0.8623 | 0.090 | 7.491 |

값은 유효 질문 macro 필수 fact 회수율이다. micro·전체 근거 성공률·부분coverage·P/R/MRR/nDCG와 각 분모, K5/10/20, 문자 예산400/800/1600은 각 summary/query JSON에 함께 보존했다. 보조 qrels는 설정마다 관련 청크 수가 달라지므로 단독 우승 기준으로 사용하지 않는다.

| Holdout 설정 | 검색기 | fact@5 | fact800자 | 유효/N/A |
|---|---|---:|---:|---:|
| fixed-400-80 | bm25 | 0.8000 | 0.5000 | 10/2 |
| fixed-400-80 | dense | 0.8000 | 0.6000 | 10/2 |
| structure-0 | bm25 | 0.9000 | 0.9000 | 10/2 |
| structure-0 | dense | 1.0000 | 0.8000 | 10/2 |

## 실제 학습 사례

생일 휴가의 자격·신청 기한·사용 기간 종합 질문에서 Dense top5는 fixed400/80이2/3 fact, structure0이3/3 fact를 회수했다. 기준선은 경계에서 잘린 적용 조건을 top5 합집합으로도 모두 덮지 못했다. 이 화면 비교에서 중복은160자 대0자였다. 그러나800자 whole-chunk 예산에서는 둘 다1/3이었다. top-k 개선만으로 제한된 전달 분량의 근거 누락까지 해결됐다고 해석하면 안 된다.

LLM0은621개, 평균 약62.1자,200자 미만99.84%로 과분할했다. Dense@5는0.3696으로 기준선보다 낮았다. LLM80의 회수율은0.8406으로 올라갔지만 중복과 청크 수 비용이 있다. 의미 기반/LLM이라는 이름이 품질 향상을 보장하지 않는다. 원문·질문·임계값을 이 결과에 맞춰 바꾸지 않았다.

## 실제 모델·비용·실패

- LLM 108/219 요청, 1326.96/7200초. 준비3회+실제105창 요청. 독립 전체 실행3회, 각35창, 재시도0회. 대표는 검색을 보기 전에 최초 성공 실행으로 고정했다.
- 본 실행105요청의 관측 입력토큰 155,085, 출력토큰 18,027. 준비 probe의 별도 usage는 probe-results.json에 있다. 입력 상한6510은 UTF-8 기반 보수적 bound이며 정확 tokenizer 수치라고 부르지 않는다.
- 임베딩 2773/32000item, 96요청(준비1회2item 포함), 183.96/1800초. 문서/단위/질문 cache hit는 각 artifact에 기록했다.
- 최종 저장 시점 검색 누계 1634/2328. 이후 사용자 수동 실험은 런타임 ledger에 추가된다.
- LLM3반복은 강제window 경계34개 및문서양끝을 제외한 Jaccard1.0,3/3쌍 정확일치. 관측한 세 번의 일치이며 모델의 보편적 결정성을 보장하지 않는다. 저장 재생은 반복에 포함하지 않았다.
- experiment-001은 첫 Dense 반복의 점수 약2e-16 차이를 순위 변화로 오인해 중단됐다. 실패 보존 후 순위ID 비교와 원점수 기록을 분리해 experiment-002를 완료했다. 그리드·정답·원문·선정 규칙은 바꾸지 않았으며 기존14청크 결과를 재사용했다.
- 랭킹 지연은 이미 적재된 인덱스의 검색 연산 시간이다. index load,embedding/index build,모델 load_duration을 별도 기록했다. OS cache를 강제 비우지 않았고 HTTP 왕복/모델 임베딩 지연을 포함한 서비스 전체 속도라고 부르지 않는다.
- Python 실험 프로세스 peak RSS 209,928,192bytes. 제공자 프로세스는2초 간격 RSS 관측합 최대 4,493,049,856bytes; 샘플 이전 구간/순간 peak를 보장하지 않으며 공유 메모리가 중복 합산될 수 있다. 메모리 확대나 모델 다운로드는 하지 않았다.
- 로컬 실행의 호출·토큰·시간을 보고하며 금전 비용을 추정하지 않는다.

## 검증과 한계

- 단계58개 독립/회귀 테스트와 기존 Naive LangChain107개 테스트 PASS. 알고리즘경계/Unicode/coverage, OR/AND 지표 수작업기대값, BM25수식/알려진Qdrant벡터, 정답·policy-map 읽기차단 spy, timeout후재호출차단, API보안·작업실패/재시작을 포함한다.
- 임시 폴더 독립 복사+외부Python 새venv에서 CLI/API/모델 metadata 확인 PASS. 부모단계 Python import 없이동작; 모델추론0회. 별도BM25 검색을원래ledger에합산했다.
- 기존394개파일과 원래/LC4개색인의 P011 logical hash 보존 PASS. source-v3/v4와 Naive는수정하지않았다.
- 실제브라우저: PDF→페이지추출→청크역추적, 고정overlap80자강조, LLMfresh35요청·재생0회, 새로고침같은job, Dense/BM25 A/B, 빈결과N/A,1200/390px 가로넘침없음, Tab/Enter검색 확인. 모델실패/잘못된설정/버전불일치는 별도복사본 오류fixture에서 UI표시확인; 실제모델성공근거와구분한다.
- 원본 PDF 다운로드는브라우저경로확인. ZIP브라우저완료이벤트는불안정하여완료로기록하지않았으며 API ZIP의파일허용목록/해시는검증PASS했다. 오류fixture8004서버는종료했고 실제UI는8003에유지한다.
- 합성문서1개/작은질문세트이며 실제문서 전체의 우수성, 답변정확성, Faithfulness를평가한것이아니다. P013사람승인정답을대체하지않는다.

## 완료 증거 연결

| 체크 | 근거 |
|---|---|
| C1 | tests-stage-final.log, 모든 chunk run의 source-map/statistics/manifest, LLM boundary-details |
| C2 | tests-stage-final.log(test_span_metrics/test_retrieval_contract), tuning/holdout query qrels·분모 |
| C3 | experiment-001 실패 + experiment-002 전체 결과, llm-stability.json, ledger-final.json, memory-samples.json |
| C4 | LEARNING.md, preservation.json, index-preservation.json, tests-naive-langchain.log, standalone.json |
| C5 | browser-*.png, browser-verification.json, ui-job*.json, ui-comparisons, download-validation.json |
| C6 | exact-adoption/harness-final.log, 고정입력provenance·stage-manifest·handoff.json, 최종Git hook/queue |
