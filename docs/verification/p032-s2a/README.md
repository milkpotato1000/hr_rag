# P032 S2a — 모델 없는 청킹 준비 결과

정확 READY `fbcb82a000f31bb9e0d26da38e831caedbfbe698`, 채택 `cd1ffff`, 착수 기록 `6309757`에 따른 독립 준비다. S1 최종 결과 `3ce2ed8`과 실패·ledger·deadline·73worker 사용량을 보존한다. S2 실제 추론, LLM 선택, S3 Drive 연결과 P032 전체 완료를 뜻하지 않는다.

- [사람이 읽는 보고서](report.html), [학습 안내](../../learning/rag-package/chunk-boundaries-s2a.md)
- [준비 요약](run001/summary.json), [독립 검증](verification.json), [화면 관찰](browser-checks.json)
- [규칙 통계](run001/rule-statistics.json), [38fact × 3방식 경계 대조](run001/fact-boundaries.json), [원문 사례](run001/boundary-examples.json)
- [LLM 34window × local/API body와 fingerprint](run001/llm-window-diagnostics.json), [preview 결과](run001/preview-outcomes.json)
- [후속 workload](run001/workload.json), [고정 청크 재사용 경계](run001/fixed-reuse.json)

## 실제 산출물과 미실행

`run001/chunks/{fixed,recursive,structure}`는 각각 201/257/264개의 실제 규칙 artifact다. 공통 size256/overlap64이며 세 방식의 overlap 의미는 다르다. 모든 원문 38,582자를 덮고 공백 제외·비공백 누락은0이다. 중복 문자는 각각12,800/16,371/16,064자다. 진단 unit의 강제 분할 수와 실제 규칙 경계 분할 수는 별도 필드로 기록했다.

semantic preview는567units, 예상 경계 embedding1job, E5 max_chunks5000 이내다. LLM local/API preview는 각각34window로 최대64 안이며 body 최대5948/5888byte로16384 이내다. 모든 토큰 수null. 예시 identity의 `example_requires_configuration`과 placeholder 모델을 보존했다. API 예시는 설치 sample llm-api.json에서 schema2와 chunking 역할만 추가했다. 어떤 실제 모델 선택/검증/키 조회도 하지 않았다.

미리보기와 규칙 청킹은 설치된 wheel `9342add625a9ed633dffb2fccb3bad27379e8cddaf9a06836ea5a224fe9f280a`의 CLI `main`과 동일 코어를 사용했다. Python `-I`, source 없는 `/private/tmp` cwd, site-packages import를 assert했다. `run001/cli/`에 argv·종료 코드·출력을 저장했다. 제품 코드 변경·전체 회귀 재실행·설치 재빌드는 없다.

## 호출 차단과 보존

`prepare.py`는 socket·subprocess·모델 import·embedding/reranker/LLM·index/query·환경 credential 접근을 차단한 뒤 실행했다. 차단 대상에 진입한 횟수0, 실제 호출0이다. E5 파일은 기존 준비 경로에서 hash/config만 읽었으며 모델을 인스턴스화하지 않았다. private runtime 참조는 `.rag-runs/p032-s2a/run001/`에 두고 공개 예시는 비실행 placeholder 경로다. 가중치·키는 산출물에 포함하지 않는다.

`verify.py`는 별도의 위치 집합과 조합 완전 탐색으로114개 fact×방식 행을 대조하고68개 request body의 byte/순서를 검증했다. 준비 스크립트의 bitmask BFS를 재사용하지 않았다. 마지막에8개 guard canary를 실행해 실제 작업 이전 예외를 확인했다. 이것은 모델/키/네트워크 호출이 아니라 차단기 시험이다. S1 전체3521파일과 기존1513보존 파일 hash가 변하지 않았음을 확인했다. source snapshot 복사, page/heading mapping hash, 원문·facts·questions identity를 요약에 기록했다. 기존 chunk qrels를 새 fingerprint에 복사하지 않았다.

화면 검증은 준비와 분리된 소유 loopback UI/정적 보고서에서 저장 artifact만 읽었다. 외부 네트워크/모델/검색/키 호출0이며 loopback HTTP 관찰 자체를 네트워크 요청0이라고 계산하지 않는다. 설치 UI에서 고정 청크192–448→원문1페이지 offset192 연결, semantic567units/LLM34window preview와 ready3종만 선택되는 상태를 확인했다. 보고서의 기본 접힘·Enter/Space·Tab, 보고서/UI390px와 가로 넘침 없음도 관찰했다. 파일 선택창은 사용하지 않았고 P029 C4 BLOCKED는 유지한다. 소유 서버는 종료했다.

## 실패도 보존

`prepare-attempt001.log`: 차단기에서 socket 클래스를 함수로 대체하여 표준 ssl 모듈의 클래스 정의가 실패했다. 원문/모델 작업 전 실패이며, socket subclass의 생성자를 차단하도록 evidence runner만 수정했다. `prepare-attempt002.log`는 PASS다. `ui-attempt001.log`: sandbox loopback bind가 port_unavailable로 거부됐다. 소유 loopback 검증 권한을 적용해 재실행했고 실제 모델 요청은 없었다. 기존 실패나 S1 결과를 덮어쓰지 않았다.

## 모델 없는 재검증

S1 설치 환경의 Python 경로는 `run001/summary.json`에 있다. 그 Python으로 source 없는 cwd에서 다음 두 스크립트를 실행할 수 있다. 예시 경로는 저장소의 실제 절대 경로로 치환한다.

```sh
<installed-python> -I <dev>/docs/verification/p032-s2a/verify.py
<installed-python> -I <dev>/docs/verification/p032-s2a/report.py
```

`prepare.py`는 기존 결과가 있으면 덮어쓰기를 거부한다. 재검증은 위 verify/replay를 사용한다. source 원문 끝 공백과 봉인 JSON을 수정하지 않는다. 새 실험/실제 모델 실행은 별도 READY 이후다.
