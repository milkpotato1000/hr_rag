# P023 필수·보충 정답과 채점 정책 v1

정책 ID는 `p023-core-supplement-v1`이다. P023은 분류 검토본/정책 전달만 구현하고 실제 LLM 평가·매칭·집계 구현은 DRAFT P013의 후속 준비/채택 범위다. P013의 기존 전부 필수 reference P/R/F1 초안과 충돌하는 질문별 채점 범위는 이 정책으로 대체한다. 과거 결과를 소급 재채점하지 않는다.

## 1. 역할과 매칭

- `required`: 질문에 직접 답하거나 그 답의 조건·예외를 보존하는 사실. 누락 시 핵심 Recall 감점.
- `supplementary`: 유용한 절차·설명·관련 정보. 누락 시 감점 없고 핵심 점수 가산도 없다. 참인 보충과 다른 거짓 문장을 비슷하다는 이유로 같은 optional 항목으로 제외하지 않는다.
- 생성 claim의 역할과 사실 판정은 reference role과 별개다. 질문의 필수 의도에 대한 올바른/틀린/부분적인 답은 핵심 범위다. 승인된 보충 항목과 의미 동등한 생성은 `accepted_supplement`로 핵심 분모에서 제외한다. 필수 질문에 잘못 답한 주장을 보충으로 회피할 수 없다.
- 나머지 생성 정보는 알려진 원문과의 사실 일치·관련성을 별도 검토한다. 새로운 사실인데 reference에 없다는 이유만으로 FP/오답을 단정하지 않는다. 범위 또는 사실성이 미확정이면 사유·ID와 `review_required`를 기록한다. 원문이 불완전해 판정 불능인 것은 모순과 다르다.
- 원자성·조건/수치/부정·고유 의미 중복 정규화는 P022/P013 규칙을 따른다. 조건이 생략된 상위 일반화를 동등 처리하지 않는다. 일치 그래프의 최대 일대일 매칭·동률 claim ID 사전순과 선택 간선을 저장한다. 필수/보충 중복 매칭은 필수 우선이며 동일 의미 반복은 가산하지 않는다.

## 2. 핵심 Correctness와 의도 충족

고유 필수 정답 수 R, 핵심 범위의 고유 생성 수 G, 동등 매칭 수 M을 사용한다. `TP=M`, `FP=G-M`, `FN=R-M`; `core_precision=M/G`, `core_recall=M/R`, `core_f1=2M/(G+R)`이다. partial은 자동 소수 가산하지 않고 미매칭/진단으로 둔다. uncertain은 정상 different와 구분하며 관련된 판정/범위 미확정이 있으면 핵심 최종 점수 null/review_required, 진단/잠정 수만 남긴다.

범위가 명확하고 G=0,R>0이면 P=null,R=0,F1=0; G>0,R=0이면 P=0,R=null,F1=0; G=R=0이면 세 값 null/no_reference_claims다. gt09/10은 후자의 일반 수식으로 정답을 판정하지 않고 answerability/보류 적절성을 별도 평가한다. 모르는 질문에 숫자를 만든 실패는 claim0이라도 드러나야 한다.

의도별 모든 필수 claim이 충족됐을 때만 그 의도를 complete로 표시한다. `intent_coverage=완전 충족 의도 수/의도 수`는 보조 진단이며 핵심 claim Recall과 혼용하지 않는다. gt01의4의도/6사실을 구분한다. 초기 정책에는 의도/중요도 가중치와 임의 종합 점수를 도입하지 않는다. macro/micro는 유효 core 범위만 사용하고 제외/보류 사례·분모를 공개한다.

## 3. 모든 생성 정보를 검증하는 별도 축

Faithfulness·Neutral rate·Contradiction rate는 필수/보충/추가 생성 사실 전체에 대해 실제 전달 문맥만을 premise로 계산한다. optional을 분모에서 빼지 않는다. P013 E/T·U/T·C/T, 판정 불능 시 null/incomplete, claim0/no_claims 및 macro/micro 규칙을 유지한다.

추가 정보는 `accepted_supplement / other_source_supported / source_contradicted / unverifiable / irrelevant` 같은 사실성과 관련성의 별도 필드로 기록한다(서로 다른 축은 중복 표시 가능). source 검증은 원문 버전과 근거를 사용하며 실제 전달 문맥 기반 Faithfulness와 구분한다. 문맥에 없으나 원문에 맞는 보충은 faithful neutral일 수 있고, 원문과 다른 문맥에 기대어 말한 주장은 faithful이어도 원문 사실성 오류일 수 있다.

핵심 점수가1이어도 추가 정보 오류·미확정이 있으면 각각 `additional_factual_error / review_required` 경고와 해당 원문/claim을 함께 표시하고 “답변 전체 정답”으로 요약하지 않는다. 필수 정보의 잘못된 답은 core FP/FN에도 반영한다. unrelated이지만 참인 장황한 정보는 관련성/간결성 문제로 기록하고 거짓으로 취급하지 않는다. unknown은 추가 생성의 범위/사실 판단이 해결될 때까지 전체 검토 완료를 표시하지 않는다.

## 4. 사전 고정 기대 예시

아래는 gt01의 필수6개 기준 독립 기대값이며 실제 모델 실행 결과가 아니다. P023 보고서에는 설명 예시로, P013에서는 산술 fixture와 실제 판정 검증을 구분해 재현한다. 모든 참인 보충은 그 참 여부가 확인되고 잘못된 핵심 답과 중복되지 않는 조건이다.

| ID | 생성 내용 | G/R/M | 핵심 P/R/F1 | 추가 처리 |
| --- | --- | --- | --- | --- |
| core_all | 필수6개만 정확 | 6/6/6 | 1/1/1 | 질문 의도4/4 |
| core_plus_optional | 필수6개+참인 신청 경로1개 | 6/6/6 | 1/1/1 | 보충1, 실제 제공 문맥7개 모두 지지 시 Faithfulness1 |
| missing_probation | 필수 중 수습 제외만 누락 | 5/6/5 | 1,5/6,10/11 | 의도3/4; “모두 가능”을 추가 주장한 경우는 별도 오류 |
| wrong_deadline | 필수 중 3영업일을 1영업일로 잘못 답함 | 6/6/5 | 5/6,5/6,5/6 | 핵심 FP1/FN1, 사실 오류 |
| wrong_optional | 필수6개+팀장 승인 불필요라고 추가 | 6/6/6 | 1/1/1 | additional_factual_error, 전체 정답 표시 금지; 참 optional로 면제 불가 |
| unknown_extra | 필수6개+원문 미명시 금액 추가 | 6/6/6 잠정 | 범위까지 명확하면 core1, 전체 review_required | 범위도 미확정이면 core도 null/review_required |
| optional_only | 참인 신청 경로만 답함 | 0/6/0 | null,0,0 | 의도0/4; 보충으로 누락을 보상하지 않음 |
| no_claims | 답변 사실 주장0 | 0/6/0 | null,0,0 | Faithfulness null/no_claims |
| duplicate_core | 필수6개와 같은 사실 반복 | 6/6/6 | 1/1/1 | 중복 발생 span·반복 수 진단, 점수 증가 없음 |
| same_deadline_clarification | 필수6개+익월 이월불가 재설명 | 6/6/6 | 1/1/1 | 선택 설명/중복 관계 유지, 핵심 가산 없음 |

독립 fixture는 core_wrong FP/FN, partial·uncertain, 추가 오류·보충 매칭 위장, 알 수 없는 extra, 보류 질문, macro/micro·0분모까지 검증해야 한다. P013의 기존 합성3정답 생일 예시는 별도의 명시 정책/정답 버전 fixture로 유지하며 이 실제 gt01 6개와 섞지 않는다.

## 5. 승인·버전 경계

분류는 Codex의 위임 검토 결과다. run003 gt01 1~5번의 명시 승인은 parent/ID/text/source를 포함해 별도 이력으로 보존하고 새 패킷 전체 human_approval로 승계하지 않는다. 위임 범위와 실제 사람 관찰·정답 승인을 구분해 표시한다. P013 READY의 실제 승인 정답/평가기 라벨·holdout·모델 상한 등 기존 준비 게이트를 유지한다. 출력에 source/GT/policy hashes와 scope를 저장하고 구/신 분모의 점수를 동일 버전인 것처럼 비교하지 않는다.
