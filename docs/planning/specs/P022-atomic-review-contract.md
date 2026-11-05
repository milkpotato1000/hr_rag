# P022 원자화 검토본 실행 계약

상태: READY / P021 완료 후 dev exact adoption 범위. 2026-11-05 사용자 직접 전달·수정 진행 지시를 따른다. [P카드](../plans/P022.md), [전수 검수](../reviews/P022-atomicity-audit.md), [45개 입력별 제안](../reviews/p022/run002-atomicity-audit.json)이 의미 기준이다. 실제 사람 정답 승인은 포함하지 않는다.

## 1. 고정 입력·출력

- 입력 parent: `evaluation/project_b/preparation/artifacts/run002/packet.json`, 패킷 SHA `e6a264387d3dd169168bcf1733156bf91bd4bdf76fc8bb70f5a704e3bc7a2b0e`. 파일 SHA는 제안 JSON의 source_file_sha256과 대조한다.
- canonical: `artifacts/run001/source/extracted/canonical/hr-v4-handbook.txt`, SHA `1c6867d284d136b2eb1cf6f9a707506480946988eaa155ae46b13ce25e2eb298`. 기존 페이지 manifest와 source_spans의 조항 범위를 함께 사용한다.
- 출력: 같은 preparation 폴더의 새 `artifacts/run003/`. 기존 경로가 다른 내용으로 존재하면 덮어쓰지 않고 실패한다. 같은 검증된 결과의 verify/report 재생은 멱등으로 허용한다.
- 필수 산출물: packet.json, revision-mapping.json, atomicity-audit.json(채택한 제안의 동결 복사본), packet-manifest.json, review.html. packet은 schema_version=2, review_version=p022-atomic-v1로 구분한다. manifest는 위 산출물의 파일 hash·패킷 hash·parent 패킷 hash·원자화 제안 hash를 연결하며 자기 파일 hash를 순환 참조하지 않는다.
- parent는 run002, 과거 모델/원문/ledger는 run001을 참조한다. run001/run002 파일은 byte-identical로 보존한다. 새 실험으로 가장하거나 Qwen 초안 provenance를 Codex 신규 생성으로 바꾸지 않는다. 새 개정의 작성 방법은 Codex 원문 재검수이며 new_model_requests=0이다.

## 2. ID와 의미 변환

제안의 split10개는 각 parent claim 순서대로 `<old_id>-a1`, `-a2`, 필요하면 `-a3`를 부여한다. restore_scope2개·keep33개는 기존ID를 유지한다. old_id를 세 자식 중 하나의 ID로 재사용하지 않는다. proposal_id와 runtime ID의 대응을 매핑에 남긴다.

제안의 proposed_claims 순서/문장을 그대로 기준으로 하며, 질문 순서·유지 항목 순서와 분리 항목의 원래 위치를 보존한다. 질문별 claim 수는 gt01~gt10=(10,3,9,6,4,7,8,10,0,0), 전체57개다. keep33개는 text·source metadata를 그대로 유지하고 answer_span만 새 답변 위치에 맞춘다. restore_scope2개·split 자식은 원문을 다시 대조해 source metadata를 생성한다. 의미 변경이 필요한 경우 plan 결정으로 돌려보내며 조용히57개 조건을 맞추지 않는다.

source quote는 지정 조항 전체 범위 안에서 조건·주어·부정을 뒷받침하는 정확한 인용으로 선택하고 canonical slice/start/end·quote SHA·pages를 재검산한다. 최소 단어 수를 목표로 조건 없는 짧은 파편을 인용하지 않는다. 공유한 한 인용이 여러 독립 claim을 뒷받침할 수 있다. answer는 새 claim text를 줄바꿈으로 연결하고 각 answer_span을 다시 계산한다.

모든 구ID45개를 매핑에 한 번씩 기록하고 old claim 객체·action/reason·새 claim 객체 배열을 둔다. split은 일대다, keep/restore_scope는 일대일이다. 충돌·누락·새 정책/정답 추가를 거부한다. 질문/판정 후보18개·gt09/10의 미명시·claim0·human_approval=null·상태를 유지한다. 질문별 필수/선택 구분이나 점수 가중치를 추가하지 않는다.

## 3. 기존 경계와 새 버전 처리

read-only 확인 근거: dev 98dceeaf5998f69162a5e7f4d11eef55a55175da의 core.py, report.py, review_revision.py, prepare.py. 기존 grounded model schema/초안 함수에는 max8, P021 변환에는45개와 run001 parent·run002 렌더링 가정이 있다.

P022 전용 오프라인 변환/검증 경계를 추가한다. `revise-review`와 run001/run002 결과·검증은 그대로 보존하고, verify/report는 review_version을 보고 올바른 검증기로 분기한다. schema_version2/run003은 고정57개 및 질문별 기대 수로 검증한다. 과거 모델 응답의 max8 제약을 전역 완화하거나 model lock/prompt/요청 schema를 바꾸지 않는다. 알 수 없는 review_version이나 schema/매핑 불일치는 거부한다.

새 CLI 인터페이스는 다음과 같이 고정한다. 실행 위치는 dev 저장소 루트다.

```sh
python3 -B evaluation/project_b/preparation/prepare.py revise-atomic-review --parent evaluation/project_b/preparation/artifacts/run002 --audit docs/planning/reviews/p022/run002-atomicity-audit.json --out evaluation/project_b/preparation/artifacts/run003
python3 -B evaluation/project_b/preparation/prepare.py verify --out evaluation/project_b/preparation/artifacts/run003
python3 -B evaluation/project_b/preparation/prepare.py report --out evaluation/project_b/preparation/artifacts/run003
python3 -B -m unittest discover -s evaluation/project_b/preparation -p 'test_*.py' -v
```

run003에 대한 run/revise-ground는 모델/네트워크 실행 이전에 거부한다. audit를 생성 시 내부에 동결하므로 이후 verify/report는 외부 plan 작업폴더나 문서 경로를 요구하지 않는다. preparation 전체를 임시 경로에 복사해 run001/run002/run003을 같은 상대 위치로 유지했을 때 독립 오프라인 재생해야 한다.

## 4. 읽기 화면과 검증

새 화면은 검토본003·질문10·정답 주장57·판정18·사람 미승인과 모델 호출0회를 명시한다. 질문→원자 주장→근거 조항/페이지/인용은 펼치고 기술/실험 이력은 접는다. 각 새 claim은 원래claim과 분리 사유를 추적할 수 있다. run002 링크와 구신ID 매핑 링크를 제공한다. 모델 실패 기록은 역사적 run001 측정치로 구분한다.

오프라인 회귀는 의미/개수/ID·범위 일반화 방지, source/answer spans·pages/hash, embedded packet/HTML/manifest, 미승인 유지·판정18개/gt09/10 불변, 알 수 없는 버전·손상 입력·기존 출력 덮어쓰기 거부·실패 시 원본 보존·결정적 재생을 포함한다. 네트워크/모델 실행이 호출되면 실패하는 검사와 디렉터리 복사 재생을 둔다.

화면 검증은 현재 허용된 브라우저/네이티브 UI 도구로 run002의 남은 P021 C1을 먼저 확인하고, run003의 질문 탐색·gt01의 분리된3항목·57개 렌더링·근거 펼침·로그 기본 접힘·키보드 열기/닫기·좁은 폭/줄바꿈을 확인한다. 도구 정책 거부/미실행이면 그 증거를 남기며 검증을 우회하거나 소스 검사만으로 PASS 처리하지 않는다. 필요시 사용자의 브라우저/앱 UI에 정상적인 로컬 파일 열기를 요청할 수 있으나, 보안 보호를 끄거나 제한을 피하려고 임시 서버를 띄우지 않는다.

증거는 `docs/verification/p022/`에 source/parent 보존 인벤토리·테스트/오프라인 재생·화면 증거·manifest/전달 경로·guard/큐·push 근거로 남긴다. 기존 P021 FAIL과 증거는 보존하고 새 PASS가 있을 때만 완료한다. P013은 새 패킷 승인 전 DRAFT이며 실제 평가/추출 모델 실험을 시작하지 않는다. 서버 재시작·다운로드·모델 호출0회, main 승격 없음.
