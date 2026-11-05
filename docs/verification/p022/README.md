# P022 run003 구현과 검증 — 완료

2026-11-05 후속 확인: 사용자가 run003의 네 가지 UI 동작을 직접 정상 확인했다.
`run003-user-ui-observation.json`에 실제 사용자 응답·정확한 패킷/manifest hash·확인 범위를
기록했다. Codex 도구의 정책 차단과 C3 FAIL은 보존한다. 이 실제 인간 관찰로 남은
C3를 충족해 P022를 완료한다. 정답 내용 승인은 여전히 null이며 P013은 DRAFT다.

## 이전 구현·미관찰 기록 (보존)

2026-11-05. P021은 사용자 본인의 run002 네 UI 동작 정상 확인으로 완료했다
(관찰80be7d3, 완료61a6ef4). 이전 차단/미확인 기록은 아래에 보존한다.
그 후 exact plan1308141b6957의 P022 구현을 진행했다.

- run003의 schema2 / p022-atomic-v1과57개 후보,45개 구ID 전수 매핑을 생성했다.
- keep33개는 text/source metadata 유지, split10개와 조건 복원2개는 전체 조항을 재검수해 정확한 조건 포함 인용/위치/페이지/hash를 생성했다.
- `codex-source-recheck.json`: 45개 전수 대조·57개 문장/17개 조항 원문 검수. `atomic-delivery.json`: 새 보고서 절대 경로와 패킷·파일 hash, null 승인.
- `unit-tests-final.log`: 기존24개 + 신규8개 =32개 PASS. ID/개수/조건·예외·기한/출처·answer/HTML·미승인·버전 경계·손상/덮어쓰기 거부/모델 전 조기 거부를 검사했다. 오프라인 테스트에서 소켓을 차단했다.
- `offline-atomic-replay.json`: preparation만 독립 복사해 run001/run002/run003 verify/report, 새 sibling 생성까지 수행했다. 외부 plan/Git/모델 없이 세 기존 run과 신규 생성물의 byte 일치를 확인했다.
- `preservation-before-implementation.json`, `preservation-final-implementation.json`: run001/run002 포함 기존1379파일/plan dirty4파일 hash 및 두 run의 파일 목록 동일. 모델 호출/다운로드/서버 변경0회.
- `p013-atomic-handoff.md`: 정답 후보의 승인 대상/원자화 정책/분모 차이 인계. 실제 P013/P014/P020/Hybrid는 실행하지 않았다.

새 HTML에는 질문 탐색→각 원자 주장→펼친 근거, 과거 버전/개정 내역 링크와 기본 접힌
실험 기록이 있다. 구조 검사는 펼친 인용75개(주장57+판정18), 기본 닫힌 details81개와
내장 JSON 일치를 확인했다. 이는 실제 UI 관찰을 대신하지 않는다.

`run003-ui-status.json`에 새 화면/좁은 폭/Tab·Enter·Space가 미관찰임을 기록했다.
기존 file URL 도구 정책 거부 이후 동일 차단 경로를 재시도하거나 임시 서버/다른 브라우저로
우회하지 않았다. run002 사용자 관찰을 run003에 자동 적용하지 않았다.
따라서 P022 C3의 실제 UI 검증과 전체 완료는 남겨 둔다. 새 후보 자체의 사람 승인도 null이다.

## 초기 수신·선행 대기 기록 (보존)

# P022 수신·채택과 선행 검증 대기

2026-11-05. READY plan `1308141b695708ab125c0a9ba1517156493d563b`를
`4b47ecf`에서 통합·정확 채택했다. 카드/준비 검토/실행 계약/45개 전수 제안/인계를 읽었다.
P022는 P021 완료 선행을 유지하며 **구현 미착수**다. run003은 생성하지 않았다.

현재 UI 인벤토리에는 run002/review.html#gt01이 앱 내 브라우저 탭2에 이미 열려 있었다.
새 파일을 열지 않고 해당 탭을 읽으려고 `cua.getTab("2", {browser:"iab"})`를 호출했지만,
도구가 `Blocked browser navigation by Browser Use URL policy: file:///.../run002/review.html#gt01`
로 거부했다. 기존 P021의 file URL 생성 거부에 이어 기존 탭 읽기도 차단됨을 확인했다.
실제 렌더링/좁은 폭/키보드 접기 동작은 여전히 미확인이다. 보안 제한을 피해 다른
브라우저 표면/임시 서버/직접 CDP/별도 자동화로 같은 결과를 얻으려는 시도는 하지 않았다.

P022 실행 계약4절은 정책 거부 시 근거를 남기고 실제 검증 없이 PASS 처리하지 않도록
규정한다. 따라서 P021 C1은 미완료이고 P022는 WAITING이다. 사용자에게 현재 보고서의
순서/펼친 근거/접힌 로그/좁은 창/Tab·Enter·Space 동작의 실제 관찰 결과를 요청했다.
이 요청은 정답 데이터의 사람 승인을 뜻하지 않는다. 사용자 관찰이 도착하면 실제
범위/문제 여부를 기록하고 P021 완료 조건을 확인한 뒤 P022를 구현한다.

`receipt.json`은 채택/차단 상태와 실제 시도, `receipt-preservation.json`은 run001/run002
전체와 청킹 budget ledger 및 plan dirty4파일의 이전 hash다. 기록 시 전부 재대조했다.
새 모델 호출·다운로드·서버 변경0회. 새 데이터/코드/테스트나 P013 실행은 없다.

접수 로그 작성 중 STATE의 evidence 칸에 경로를 넣어 guard가 거부했다. 미커밋 로그의
형식을 STATE/NOTE/- 규칙에 맞추고 경로를 설명 칸으로 옮겼다. 보호 규칙은 변경하지 않았다.

이후 미착수 카드에 실행 로그가 존재한다는 검사도 거부됐다. P022는 미착수이므로
해당 새 실행 로그를 제거하고 수신/선행 대기 정보는 이 증거에만 남겼다. P021의 기존
실패와 추가 검증 실패 로그는 보존했다. 초기 거부는 guard-initial.log에 모두 보존한다.

2026-11-05 사용자 응답: “아직 확인하지 못함”. 이를 화면 검증 또는 승인으로 간주하지
않으며 P021 3/4 진행 중, P022 0/4 WAITING, run003 미생성을 유지한다.
