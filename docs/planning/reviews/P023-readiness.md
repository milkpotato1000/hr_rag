# P023 준비 검토 — 2026-11-05

사용자는 전수 분류·채점 정책의 plan 반영과 기존 dev 직접 전달·새 검토본 수정을 명시 요청했다. 이는 이 HR RAG P023의 구현/검증/정상 dev push까지 권한이며 다른 프로젝트/하네스·P013 모델 실행으로 확대하지 않는다.

## 입력·선행·역할

plan은 plan 역할을 유지한다. 동일 프로젝트 기존 `[dev] hr_rag`가 local host/동일 workspace의 dev 역할이며 현재 idle임을 호스트 목록에서 확인했다. dev HEAD=personal/dev=`dfe5e48effe84f83edb314bb8a428eee42d5531d`, clean, exact adopted plan=`1308141b695708ab125c0a9ba1517156493d563b`다. P022는4/4 완료, P013은DRAFT다. 큐의 새 요구 대기는0이며 명시 중지/미결 결정은 관측되지 않았다. 기존 plan의 무관한4개 dirty 문서를 보존한다.

## 전수 의미 검토

run003의 질문/기존57개 원자 주장과 BD/AN/RM/WF/ED/TR 원문 근거를 읽고 질문 요구/조건/예외와 직접 연결했다. 항목별 역할과 사유·의도 연결을 audit에 동결했다. 필수38/보충19 및 질문별 개수는 전수 합과 일치한다. 원문 위치와 텍스트는 바꾸지 않으며 gt09/10의 claim0·미명시 후보와 판정18개를 유지한다. 의도 수를 사실 수로 오인하지 않는다.

P022 완료 계약은 필수/보충 정책을 범위 밖으로 명시했으므로 후속 P023로 관리한다. P013은 새 선행/정책을 연결하되 DRAFT 유지다. 기존 승인 과정·평가기 검증·모델 실행 상한은 대체하지 않는다.

## 준비 완료 판단

[실행 계약](../specs/P023-scoped-review-contract.md)은 고정 parent/audit hashes·schema3/run004·기존ID/source/answer 보존·새 rubric/표시·CLI/독립 오프라인 재생/버전 격리·실제 화면·실패/보존·완료 증거를 확정한다. [정책](../specs/P023-scoring-policy.md)은 core P/R/F1·선택 제외·오류/미확정 처리·전체 생성의 E/U/C·0분모·보류·별도 의도진단·고정예시를 확정한다. 새로운 모델/비용/업무 결정은 필요 없다. 정확한 READY 커밋 채택 후 P023만 착수 가능하다.

## 검증 범위

plan 검증은57개 유일ID/텍스트/source 매칭·필수/보충 완전분할·의도/참조·질문별 수·parent/file/canonical hashes·관련 문서 링크·diff/guard/큐다. 이것은 제품 구현 테스트나 실제 UI PASS가 아니다. dev는 별도 회귀/독립 재생·실제 화면 확인을 수행하고 실패를 보존한다. 직접 사람의 run003 승인5개와 이번 판단 위임을 새 전체 사람 승인으로 가장하지 않는다.

실제 plan 읽기 검증 결과 PASS: parent 논리/파일 hash·canonical hash,57개 유일 ID/text/source 일치와 canonical 정확 slice/quote SHA,38/19 및 의도 연결, 상대 문서 링크, git diff --check, contract_guard check. 큐는 dev 다음 작업 P023/새 요구 대기0을 표시한다. 제품 회귀/모델/UI는 plan에서 실행하지 않았다.

## 직접 인계

카드/실행 계약/분류 audit/정책/준비 검토를 포함하는 full READY SHA를 커밋·정상 plan push 후 검증한 기존 dev에 직접 전달한다. SENT/ACK/ADOPTED/완료는 실제 관찰 후 [인계](../handoffs/P023.md)에 구분 기록한다. plan push만으로 dev 전달·구현 완료를 주장하지 않는다.
