# P013 인계 — 필수·보충 정답과 검증 축

P023의 검토본은 preparation/artifacts/run004/packet.json이다. 실제 GT 전체 승인은null,
P013은DRAFT다. 새 패킷/정책/manifest의 정확 hash는 delivery.json에 기록한다.

- 버전 schema3 / p023-core-supplement-v1. 원문·57개 기존 ID/text/source/answer_span·전체 answer 유지.
- 필수38/보충19. 질문별6/4,3/0,8/1,2/4,4/0,3/4,4/4,8/2,0/0,0/0. 의도·역할·사유·설명 관계와 별도 required_answer/supplementary_answer가 있다.
- 핵심은 고유 필수 R/핵심 생성 G/동등 매칭 M의 P=M/G,R=M/R,F1=2M/(G+R). 정확한 accepted_supplement는 핵심 가산/누락 감점에서 제외한다. 틀린 핵심 답을 보충으로 숨기지 않는다.
- 전체 생성 E/U/C는 실제 전달 문맥을 premise로 모든 필수/보충/추가 claim을 포함한다. 원문 사실성과 전달 문맥 지지 여부는 별도다.
- 핵심 만점이어도 잘못된 보충/추가 사실은 additional_factual_error 경고로 드러낸다. 범위/사실성 미확정은 review_required, 관련 core 미확정은 최종 null이다. reference에 없다는 이유만으로 새로운 사실을 오답으로 단정하지 않는다.
- partial/uncertain·동일 의미 중복·일대일 매칭·필수 우선·의도 완전충족·0분모·answerability/보류·macro/micro 규칙은 동결 scoring-policy.md를 따른다. 임의 가중치/종합 점수는 없다.
- 고정 gt01의4의도/6필수와10개 기대 예시는 설명·후속 fixture다. 이번에 실제 채점기를 구현/모델 호출/재채점하지 않았다. 과거3정답 합성 fixture와 섞지 않는다.

부모 run003에서 직접 승인된 gt01 첫5개는 정확한 parent/ID/text/source 역사로만 보존한다.
새57개 전체 또는 새 분류의 실제 사람 승인은 아니다. 위임 검토·정책 수락·UI 관찰과 정답
승인을 구분한다. 새 run004의 UI 관찰은 별도로 남아 있다.
P013의 승인/준비 검토/holdout·모델/호출 상한 등의 기존 게이트를 해제하지 않는다.
