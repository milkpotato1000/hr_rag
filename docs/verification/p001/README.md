# P001 검증 기록

2026-10-22 Asia/Seoul, `hr_rag-dev`의 `dev`에서 Python 3.9.6으로 실행했다.
채택 기준은 plan `99ce84f32f5cff8db0a92165fae98706dfcda89b`이며 표준 라이브러리만 사용했다.

## 결과와 재현

```sh
python3 -m unittest discover -s tests -v
python3 scripts/evaluate_retrieval.py --chunks data/synthetic/chunks.jsonl --queries data/synthetic/queries.jsonl --rankings data/synthetic/example_rankings.jsonl --k 5 10 20 --output /tmp/hr-rag-p001-example.json
python3 scripts/evaluate_retrieval.py --chunks docs/verification/p001/fixture-chunks.jsonl --queries docs/verification/p001/fixture-queries.jsonl --rankings docs/verification/p001/fixture-rankings.jsonl --k 2 5 --output /tmp/hr-rag-p001-independent.json
python3 scripts/contract_guard.py check
python3 scripts/work_queue.py --owner all --json
```

- [최초 테스트](01-initial-tests.txt): 19개 중 1개 실패. [독립 합산 및 수정](02-fixture-expectation-correction.md)에 오류 원인과 수정 근거를 기록했다. 실패와 로그를 보존했다.
- [최종 전체 테스트](03-final-tests.txt): 19개 모두 PASS. 테스트는 subprocess로 실제 CLI를 호출하며 입력 오류별 subTest를 포함한다.
- [실제 CLI 출력 기록](04-cli-transcript.txt): 정상 실행, 반복 실행 바이트 일치, 알 수 없는 참조의 종료 코드 2·stderr, 기존 결과 바이트 보존과 새 결과 미생성을 확인했다.
- [수기 예시 순위 결과](example-result.json)와 [독립 산식 fixture 결과](independent-result.json)를 그대로 저장했다.
- [기록 파일 공백 검사 및 수정](06-format-recheck.txt): 출력 기록의 마지막 빈 줄을 제거하고 staged diff 검사를 재실행해 통과했다.
- [계약 및 큐 확인](05-contract-and-queue.txt): 완료 체크·최신 PASS·근거 파일과 채택 계약을 검사한다. index 검사도 실행해 근거가 커밋 대상에 포함되는지 확인한다.

## 완료 조건별 근거

| 조건 | 실제 확인 내용 | 근거 |
| --- | --- | --- |
| C1 | 가상 표시가 있는 15청크, 6문서·주제, 14질문 중 answerable 11/unanswerable 3. 생일 자격·복수 근거·혼동 청크를 수작업 검토 | [데이터 스키마와 정답 검토](../../../data/synthetic/README.md), `test_synthetic_corpus_and_curated_example`, [테스트 출력](03-final-tests.txt) |
| C2 | 계약의 K=2/5 등급별 독립 산식, 전체 등급 0~3, relevant 위치 경계, macro query 평균 | [독립 결과](independent-result.json), [기대값 수정 이력](02-fixture-expectation-correction.md), 최종 테스트 |
| C3 | 빈·짧은 순위, K 밖 근거, 분모 K, unanswerable 지표 null·macro 제외, answerable=0 및 unanswerable=0 분모 | 최종 테스트 `test_relevant_first_kth_outside_k_empty_and_short`, `test_only_unanswerable_has_null_macro` 등 |
| C4 | 세 입력의 중복 ID·빈 파일·JSON/UTF-8/타입·불리언 등급·잘못된 참조·질문 누락·중복 순위 ID·K 오류 거부. 각 invalid fixture에서 기존 결과 보존과 새 결과 미생성 확인. 출력 충돌·교체 실패 임시 파일 정리도 검사 | 최종 테스트, [CLI 실패 기록](04-cli-transcript.txt), [의도적으로 잘못된 순위](invalid-rankings.jsonl) |
| C5 | 세 입력의 바이트 SHA-256 독립 재계산, K·버전·분모 일치. 두 실행 JSON 바이트 동일. 본문 수정 시 corpus hash 변경과 지표 보존, 참조 제거 시 거부 | `test_hashes_version_and_byte_determinism`, CLI 반복 기록, 저장한 결과 JSON |
| C6 | 사용 안내·실제 출력·최초 실패 및 수정·재검증 이력을 함께 커밋하며 worktree/index guard·큐 확인 | [프로젝트 실행 안내](../../../README.md), 본 기록, [계약 및 큐 확인](05-contract-and-queue.txt) |

`{a:3,b:1}`와 `[x,b,a]`의 독립 기대값은 구현 함수를 호출하지 않고 계약의 수식으로 검증했다.
K=2: Recall=0.5, Precision=0.5, MRR=0.5, nDCG=`(1/log2(3))/(7+1/log2(3))`.
K=5: Recall=1, Precision=0.4, MRR=0.5, nDCG=`(1/log2(3)+7/log2(4))/(7+1/log2(3))`.

수기 예시의 @5 macro는 Recall=0.9090909091, Precision=0.3090909091, MRR=0.7575757576, nDCG=0.7792868869다.
근거 없는 질문 3개 중 검색 결과 있음 1개(1/3), 빈 결과 2개(2/3)다.
이는 수기 입력 평가 예제이며 검색 품질·답변 정확도·보류 정확도 또는 실제 회사 규정의 존재 여부를 입증하지 않는다.
모델·검색 엔진 구현과 외부 연동은 P001 범위에 포함하지 않았다.
