# P002 BM25 기준선 검증

2026-10-22 Asia/Seoul. 채택 plan `02dd3f0d5bcb8bf393897bb54cdee43e340b3a35`의 개정 C1–C8을 검증했다.
제품 위치는 `1. Naive RAG/`이며 Python 3.9.6·Unicode 13.0.0과 표준 라이브러리만 사용했다.
구현 범위는 BM25 검색과 P001 평가 연결까지다. Dense·생성·에이전트나 Naive RAG 전체의 완성을 뜻하지 않는다.

## 구현과 구조 정정

기존 P001 평가기는 변경하지 않고 BM25 실행기가 그 입력 검증·지표 계산을 재사용한다.
검색은 title + LF + text와 question만 사용하며, query_id는 연결과 정렬에만 쓴다. 관련성 정답과 answerability는 평가에만 쓰인다.
고정 토큰화·산식·동점·0점 제외·top-k 정책, 결과 네 파일과 관측 시간 분리를 구현했다.

직전 세부 폴더 분리 작업 `413c82e`는 이력에 보존했다. [그때의 검증](01-stage1-preservation.txt)은 당시 경로에서 실행한 원본 그대로다.
사용자 정정 이후 여섯 제품 파일은 `1. Naive RAG/`로 이동했고 기존 바이트를 모두 보존했다.
[이전 README](02-layout-migration/previous-README.md)·[이전 manifest](02-layout-migration/previous-stage-manifest.json)와 [이동 대조](02-layout-migration/migration.json)를 남겼다.
기존 P002 착수 로그에 정정·영향을 append했고 P001 완료 카드·루트 제품·기존 증거는 변경하지 않았다.
`1. 검색 평가 기반/`은 정리했고 `2. BM25 검색 기준선/`과 미확정 후속 큰 단계는 만들지 않았다.

## 실제 검증

- [첫 통합 테스트](03-first-naive-rag-tests.txt): P001 19개 + BM25 18개 = **37 PASS**. P002 제품 구현의 예기치 않은 실패는 없었다. 오류 주입과 잘못된 입력은 예상 실패를 확인하는 테스트다.
- [독립 실행·루트 회귀·CLI 원본 출력](04-delivery/commands.txt): 루트 P001 **19 PASS**, 저장소 밖에 큰 단계 하나만 복사한 전체 테스트 **37 PASS**, BM25와 P001 CLI 정상 실행.
- [최종 대조](04-delivery/delivery-checks.json): 순위·점수·지표의 반복 바이트 일치, observations 이외 run.json 일치, 별도 P001 CLI 재평가 바이트 일치, 이전 P001 수기 결과 재현.
- [원본 보존 대조](04-delivery/preservation.json): 최초 여섯 파일의 source commit·경로·hash와 최종 단계·루트 원본 일치. P001 카드·기존 증거, 이전 메타데이터·로그 보존 및 이전 잘못 나눈 경로 제거 확인.
- [계약·큐·index 검사](05-contract-and-queue.txt): 최신 채택 plan, P001 선행 완료, P002 완료 상태·최신 PASS·커밋할 근거의 일치 확인.

테스트의 기대 점수는 BM25 계산 함수를 재사용하지 않고 계약의 식과 비교한다(절대 오차 <= 1e-12).
[같은 길이 fixture](04-delivery/independent-fixture/equal-length/scores.jsonl)의 순위는 [b,a], 점수는 각각 ln(1.6)×4.4/3.2와 ln(1.6)이다.
[길이 보정 fixture](04-delivery/independent-fixture/length-normalized/scores.jsonl)는 b=ln(1.6)×4.4/3.65, a=ln(1.6)×2.2/1.975와 일치한다.
fixture 입력과 결과 네 파일도 함께 저장했다.

평가 실패·staging 쓰기 실패·일부 최종 파일 게시 후 쓰기 실패는 mock으로 결정적으로 주입했다.
main의 stderr·종료 코드 2, 기존 사용자 파일 보존, 새 최종 결과와 임시 디렉터리 미잔존을 확인했다.
출력 경로가 preflight 이후 다른 실행에 의해 생성된 경우도 보존한다.
권한 설정만으로 실패를 가정하지 않았다. 성공한 종료 코드 0 이후 네 결과 파일을 읽으며 전체 디렉터리의 원자적 가시성은 보장하지 않는다.

## 관측한 합성 기준선

[순위](04-delivery/baseline/rankings.jsonl), [점수](04-delivery/baseline/scores.jsonl), [지표](04-delivery/baseline/metrics.json), [환경·설정·관측 시간](04-delivery/baseline/run.json).
N=15, avgdl=27.5333333333, answerable=11, unanswerable=3, top-k=20, k1=1.2, b=0.75다.

| K | Recall | Precision | MRR | nDCG |
| --- | ---: | ---: | ---: | ---: |
| 5 | 0.893939394 | 0.272727273 | 0.803030303 | 0.775828462 |
| 10 | 0.954545455 | 0.154545455 | 0.803030303 | 0.808825485 |
| 20 | 0.954545455 | 0.077272727 | 0.803030303 | 0.808825485 |

근거 없는 질문 3개 중 검색 결과가 있는 질문은 2개(2/3), 빈 결과는 1개(1/3)다.
근거 없는 질문은 검색 지표가 null이고 macro에서 제외된다. 이 비율은 답변 보류 정확도가 아니다.
관측된 지연은 run.json의 observations에만 기록했다. 단일 소규모 실행 지연으로 엔진 간 우열을 주장하지 않는다.

### 관측 사례 3개

다음 질문·정답은 [보존한 queries](<../../../1. Naive RAG/data/synthetic/queries.jsonl>), 실제 근거 본문은 [chunks](<../../../1. Naive RAG/data/synthetic/chunks.jsonl>)에서 확인할 수 있다. 순위와 토큰·점수는 위 실제 결과에 있다.

1. **q03 복수 근거의 top 5 누락**: 자격·신청 기한·사용 기간을 함께 묻는다. birthday-request·birthday-window는 각각 1·4위지만 birthday-eligibility는 6위(score=1.016212604)다. 해당 청크의 “입사 후 3개월”, “수습 중인 직원은 대상에서 제외”가 자격 근거다. top 5에는 annual-request·welfare-birthday·annual-halfday가 섞였다.
2. **q10 주변 근거 미검색**: 식대의 직접 근거 welfare-meal만 검색됐다. 등급 1의 remote-days는 검색되지 않았다. 질문 토큰은 `나오나요, 사무실, 식대가, 재택근무일과, 휴가일에도`이고 해당 청크의 “재택근무는”, “휴가가 아닌 근무일”과 정확한 토큰이 겹치지 않는다. 조사·어미를 정규화하지 않는 토큰화의 한계를 보여 준다. 정답은 수정하지 않았다.
3. **q12 근거 없음에도 결과 반환**: 배우자 출산 휴가 일수·신청 절차의 qrels는 비어 있지만 birthday-request·welfare-birthday·annual-request가 반환됐다. 이 청크들은 생일 특별휴가 신청·생일 포인트·연차 신청을 설명하며 배우자 출산 휴가의 일수를 제공하지 않는다. `신청` 같은 단어 매칭이 근거 충분성을 보장하지 않는다.

품질 임계값은 만들지 않았다. 계산·실패 정책·정답 격리·재현성과 구조 보존이 이 카드의 통과 기준이다.
작은 가상 corpus와 단순 어절 토큰화 결과를 일반 한국어 검색 품질·답변 정확도·실제 회사 제도의 존재 여부로 해석하지 않는다.

## 완료 조건별 연결

| 조건 | 근거 |
| --- | --- |
| C1 | 독립 점수·길이 보정 테스트/fixture, preservation.json의 corpus·질문 hash |
| C2 | 토큰화·동점·top-k·OOV·개별/전체 빈 토큰·중복 질문 토큰 테스트와 실제 rankings/scores |
| C3 | qrels/answerability·문서 메타데이터 변경 불변성, 실제 P001 CLI 재평가 바이트 일치 |
| C4 | 스키마·독립 hash·환경·설정·통계·유한 시간, 반복과 hash seed/입력 순서 검증 |
| C5 | 입력·옵션·기존 파일/폴더/링크·부모 부재, 평가/쓰기/게시 실패 주입·경합 보존 테스트 |
| C6 | 실제 기준선 네 파일, 세 관측 사례·한계, 이전 이력 및 모든 명령·출력 |
| C7 | 계약·큐·index 검사, P001 완료 6/6과 P002 최신 PASS 증거 |
| C8 | 이동 기록·현재 manifest·원본 보존·단독 복사 37개 및 대표 CLI 실행·이전 경로 제거 |

## 재현

저장소 루트에서 새 증거 경로를 지정한다. 기존 증거는 덮어쓰지 않는다.

```sh
python3 docs/verification/p002/verify_delivery.py --output-dir /tmp/hr-rag-p002-new-evidence
python3 scripts/contract_guard.py check
python3 scripts/work_queue.py --owner all --json
```

제품만 실행할 때는 [큰 단계 안내](<../../../1. Naive RAG/README.md>)를 따른다.
