# P013 재개 준비 검토 — READY

2026-11-27 plan 검토. 사용자가 명시적으로 재개 계획·dev 전달·8B 단독 메모리 확인 후4B 생성/8B 평가 순서를 승인했다. 기존 P013 범위 내의 자원 실패 복구와 실행 생명주기·시간 구간을 이번 계약으로 구체화했다. 새 모델/평가셋·기준 변경은 없다.

## 관찰 및 결정

- dev HEAD/personal/dev `6cad4c6d1ee36ef0c9ae864a84b8299fd069bd11`, clean. C1 PASS, C2 자원 중단, C3 미실행, C4 대기. 기존 `[dev] hr_rag`와 같은 프로젝트·경로를 호스트 목록으로 확인했다.
- run001은 extract01-r1 한 건을 정상 완료했지만 pressure4를 관측했다. ledger pending=null/unresolved=true와 call/manifest/expectations hashes를 읽기 검산했다. 첫 성공1건을 보존하고 재호출하지 않는다.
- 예전4시간 만료 때문에 이전 ledger를 해제/재설정하는 방식은 사용하지 않는다. 새 recovery lineage에 단 한 번의4시간 구간을 부여하고 parent+child 전체 예산을 검산한다. 이 변경은 실제 인간의 이번 재개 요청에 근거한다.
- 이전 정답/라벨 승인 sidecar는 그대로 유효하다. 과거 UI 확인이나 첫 실행 성공을 새 메모리/품질/결과 화면의 PASS로 승계하지 않는다.
- 새 모델 실행을 추가하지 않고 남은 extract01-r2를 probe로 사용한다. 적재·추론·유지60초를 측정한다. normal 관측/단독 ownership을 선행하고 critical/12GiB/계측 실패 중지 기준을 유지한다.
- keep_alive0→300초의 명시 transport 변경과 구간 종료 unload로 연속 cold load를 줄이는 안이다. 의미 payload·모델·token/seed/temperature·기대값을 유지하고 실제 diff를 저장한다. transport가 달라진 결과임을 표시한다. memory PASS는 작은 사례에서의 관측으로 제한한다.
- embedding과4B가 동시에 올라가지 않도록 검색 결과를 먼저 고정한다. 4B 답변/dispatch snapshot을 모두 저장하고 내려야8B 평가를 시작한다. cached retrieval↔실제 생성 문맥의 일치·오프라인 재생 검증을 필수화했다.

## 실행 상한과 영향

남은 업무 요청15+68+20+20+180=303, parent1 포함304. unload 제어4를 별도 계수해 이번 provider 작업 상한307이다. 자동 재시도0/병렬1, 새4시간 deadline은 최초 모델 작업부터 단1회 시작한다. 중지 후 자동 재개/4B 자동 전환·14B·외부 API·다운로드·server restart는 없다. 기존 서버와 사용자 앱을 강제로 종료하지 않는다.

변경 대상은 dev의 evaluator execution/ledger/lifecycle·phase orchestration·LangChain export adapter와 검증/학습 보고서다. 보호된 하네스 코드는 변경할 필요가 없다. plan은 제품 코드를 작성하거나 모델을 실행하지 않는다. 완료 C1~C4는 기존 조건을 유지하며 재개 계약6장의 검증을 해당 증거에 연결한다. 런타임/모델 버전이 다르거나 자원 조건이 안 맞으면 dev가 실측 mismatch/중단을 보고하며 임의 완화하지 않는다.

## 준비 검증

plan에서 계약/권한 hash, parent manifest·ledger·case·expectation hashes, 이미 소비된 요청과 다음 잔여 요청, 예산 산술, 기존 승인 자료 불변성·Markdown 상대 링크, diff/contract guard를 확인한다. 이 검토는 실제 메모리 PASS가 아니다. 상세 결과는 커밋 전 검증 출력을 근거로 하며 dev 구현/fixture·실행은 정확 채택 이후다.

## 전달

새 READY full SHA·재개 계약/권한·원본 보존·순서·한도와 다음 행동을 같은 기존 dev에 직접 보낸다. 반복 허가 질문은 필요 없다. 전송/수신/채택/메모리 게이트/제품 완료를 각각 관찰해 기록한다. 다른 프로젝트·역방향 메시지·새 채팅 생성 권한으로 확대하지 않는다.
