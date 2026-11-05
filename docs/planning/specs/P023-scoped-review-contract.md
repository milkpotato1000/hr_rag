# P023 분류 검토본 실행 계약

READY. [카드](../plans/P023.md), [분류 audit](../reviews/p023/run003-scope-audit.json), [채점 정책](P023-scoring-policy.md)이 기준이다. 기존 P022 산출물은 불변이며 이 카드로 새 버전만 추가한다.

## 입력과 출력

- 입력 dev commit `dfe5e48effe84f83edb314bb8a428eee42d5531d`, parent `evaluation/project_b/preparation/artifacts/run003/packet.json`.
- parent packet SHA `946d7181ecf8b45e633a347adbcc241f38dfd5976d80342e34e1da3bf2d87199`, 파일 SHA `fec84decf14335151162d9b168db366854a5b4a45d06092230e78f2e124e802b`.
- canonical SHA `1c6867d284d136b2eb1cf6f9a707506480946988eaa155ae46b13ce25e2eb298`와 원문/페이지 매핑은 P022 그대로.
- audit SHA `437bcf0eafb6de063db66e992916b7b8c5cfd00ee150490f89e2e84a0b14d0f0`.
- 출력 preparation의 새 `artifacts/run004/`. 필수 파일 packet.json, scope-audit.json(동결 audit), scoring-policy.md(채택한 정책 동결), scope-mapping.json, packet-manifest.json, review.html. packet schema_version=3, review_version=`p023-core-supplement-v1`.
- manifest는 parent packet/file·audit·policy·매핑·출력 파일 hashes를 연결한다. 자기 자신의 파일 SHA 순환 참조는 하지 않는다. packet의 논리 hash는 기존 방식처럼 자신의 packet_sha256 필드를 제외하고 계산한다.

## 변환·스키마

기존 질문10개·57개 claim ID/text/source/answer_span·codex_source_checked.answer는 변경 없이 유지한다. parent 실험/모델 실패/provenance/판정18개도 그대로 보존한다. answer 전체문장은 기존57개를 포함하므로 이 값을 새 “필수 답변”이라고 표시하지 않는다.

각 질문에 `answer_rubric`를 추가한다: policy_version, intents(id/text/required_claim_ids), required_claim_ids, supplementary_claim_ids, required_answer, supplementary_answer, counts, claim_roles(claim_id/role/intent_ids/supplement_kind/reason/clarifies_required_ids). required_answer와 supplementary_answer는 원래 순서의 해당 claim.text를 줄바꿈으로 연결해 결정적으로 생성한다. 그룹별 문장은 별도 derived 값으로 두고 기존 answer_span을 잘못 재사용하지 않는다. 모든 role/의도/사유는 audit와 정확히 일치한다.

질문별 필수/보충은 gt01~10 = `(6/4,3/0,8/1,2/4,4/0,3/4,4/4,8/2,0/0,0/0)`. 총57=38+19, 모든 ID는 둘 중 하나에 정확히 한 번 속한다. required는 반드시 한 의도 이상에 연결되고 모든 의도는 필요한 claim ID들을 가진다. 보충은 필수 coverage에 참여하지 않는다. gt01 이월불가의 clarifies_required_ids는 생일월 claim을 가리킨다.

gt09/10 answerability=unanswerable_candidate·claim0을 유지한다. 필수 답변 필드의 빈 문자열을 성공적인 답변으로 표시하지 않고 기존 “제공 규정집에 미명시” 답변과 보류 검토 안내를 보여준다. 새로운 숫자/claim을 만들지 않는다.

새 개정 메타에 parent version/hash·method=Codex delegated scope review·new_model_requests=0·policy hash·분류 저자를 저장한다. 인간 승인 원장은 자동 생성/수정하지 않는다. parent gt01의 `gt01-c02-a1/a2/a3`, `gt01-c04-a1/a2`에 대한 5개 명시 승인 이력은 별도 `prior_human_claim_reviews`로 parent hash·정확 ID/text/source와 함께 표시한다. 나머지를 직접 사람 승인으로 기록하지 않고 새 패킷/질문 human_approval=null을 유지한다. 위임 검토 완료와 미완료 실제 전체 승인을 동시에 이해할 수 있게 표시한다.

## CLI와 버전 격리

```sh
python3 -B evaluation/project_b/preparation/prepare.py revise-scoped-review --parent evaluation/project_b/preparation/artifacts/run003 --audit docs/planning/reviews/p023/run003-scope-audit.json --policy docs/planning/specs/P023-scoring-policy.md --out evaluation/project_b/preparation/artifacts/run004
python3 -B evaluation/project_b/preparation/prepare.py verify --out evaluation/project_b/preparation/artifacts/run004
python3 -B evaluation/project_b/preparation/prepare.py report --out evaluation/project_b/preparation/artifacts/run004
python3 -B -m unittest discover -s evaluation/project_b/preparation -p 'test_*.py' -v
```

새 모듈/테스트로 분리하고 기존 schema1/2·P02145개/P02257개 검증·렌더링은 그대로 동작한다. 새 review_version은 명시 분기하고 미지정/알 수 없는 버전은 거부한다. run/revise-ground 등 모델 경로에서 run004는 네트워크/모델 호출 전에 거부한다. 검증·보고서 재생은 동결 audit/policy로 독립 수행하며 외부 plan 경로에 의존하지 않는다. out이 다른 내용으로 존재하면 덮어쓰지 않고 실패한다. 기존 동일 결과의 verify/report 재생은 멱등이다. 손상 parent/audit/policy는 출력 생성 전에 거부하며 실패 시 입력과 과거 원본을 보존한다.

## 화면

첫 화면에 검토본004·질문10·필수38/보충19·전체57·미명시후보2·모델호출0을 표시한다. 질문별 질문 의도와 필수/보충 수 → 필수 답변 → 각 필수 claim/근거 → 보충 안내(없어도 감점 없음) → 각 보충 claim/근거 순서로 보여준다. 두 그룹은 색상 외 텍스트 제목/배지로 구분한다. 근거 원문은 펼쳐 보여주고 보충도 사실 검증 대상임을 명시한다. 그룹 설명/근거는 일반 화면에서 읽을 수 있고 실험·구버전·전체 원답변/산술 예시 상세는 기본 접힘으로 둘 수 있다. 분류 사유는 항목별 제공한다.

정책 설명에는 핵심 P/R/F1과 전체 생성 Faithfulness의 분모 차이, 추가 오류 경고, gt01 예시를 표시한다. 고정 기대 예시는 실제 모델 결과로 표시하지 않는다. 기존 57개를 전부 말해야 정답이라는 인상을 주는 문구를 제거한다. 이전 run003/매핑/정책 링크, 각 조항/페이지/정확 인용을 제공하고 좁은 창 줄바꿈·가로 넘침·Tab/Enter/Space details를 검사한다.

UI 도구 정책이 로컬 파일 관찰을 차단하면 우회 서버/보안 해제 없이 실패 증거를 남긴다. 새 run004에 대한 실제 사용자 관찰로 보완할 수 있지만 과거 run003 관찰을 승계하지 않는다. 관찰 미실행 상태는 구조 검사만으로 PASS 처리하지 않는다.

## 완료 증거와 제외

`docs/verification/p023/`에 parent/기존 자료 인벤토리·전수 분류 대조·source/answer/JSON/HTML/manifest 일치·손상/불변성·기존 회귀·독립 복사4버전 재생·화면·guard/큐·정상 dev push·P013 인계를 커밋한다. 실제 모델을 통한 채점·성능 평가, P013 구현/READY 전환, GT 전체 사람 승인, 실제 HR 정책 변경, server/download/model 작업은0이다. 더 나은 분류를 임의 변경하지 않고 충돌 근거를 plan에 기록한다.
