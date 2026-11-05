# P013 Neutral rate·Contradiction rate 요구 보강 검토

날짜: 2026-11-04. 근거: [plan] hr_rag에서 사용자가 “P013 플랜에 Neutral rate랑 Contradiction rate도 산식·결과 보고 항목·검증 예시까지 확실히 반영해줘”라고 요청했다.

## 범위와 결정

- 기존 P013에 두 비율을 필수 보고 지표로 추가한다. 새 P카드나 평가 모델 호출은 필요하지 않다.
- T는 중복 정규화 후 전체 평가 대상 생성 claim 수이며 E/U/C는 지지/근거 부족/모순 수다. Faithfulness=E/T, Neutral rate=U/T, Contradiction rate=C/T다. 세 비율은 동일한 분모와 유효 사례 집합을 사용한다.
- 판정 불능/실패가 있는 답변은 세 비율 모두 null/incomplete, T=0이면 null/no_claims다. 실패를 분모에서 제외해 점수를 높이거나 neutral로 치환하지 않는다.
- JSON·읽기 보고서에서 비율, E/U/C/I, T/V/coverage, 상태·사유, claim별 판정·근거를 추적한다. macro/micro와 포함/제외 수를 구분한다.
- P013 C2에는 비율 산술·경계 fixture, C3에는 JSON/읽기 보고서 일치 검증을 요구한다. Correctness의 기존 P/R/F1·매칭 정책은 유지한다.

변경 대상: [P카드](../plans/P013.md), [상세 초안5.1](../specs/P013-evaluation-draft.md#51-neutralcontradiction-rate-필수-보고-계약), [산술 fixture](../specs/P013-metric-fixtures-draft.json).

## 확인 결과

plan이 JSON을 읽고 Fraction 기반으로 기대 산술을 독립 재계산했다. 제품 평가기 구현이나 실제 모델 평가 결과가 아니다.

| 검증 | 결과 |
| --- | --- |
| E2/U1/C1, T4 | Faithfulness0.5 / Neutral0.25 / Contradiction0.25, 합계1 PASS |
| 전부 지지 / 근거 부족 / 모순 | 각각 (1,0,0) / (0,1,0) / (0,0,1) PASS |
| 주장0 / 판정 불능 포함 | 세 비율 모두 null, no_claims / incomplete 및 coverage null / 0.5 PASS |
| macro/micro | macro (2/3,1/6,1/6), micro (1/2,1/4,1/4), 포함2·제외1 PASS |
| 원본 보존 | 기존 비관련 fixture11개 동일, 기존16개 ID 유지·신규2개로 총18개, 고유 ID PASS |
| 카드 상태 | 준비 초안·실행 미착수·완료 체크0/4 유지 PASS |
| 공백/패치 검사 | git diff --check PASS |
| 계획 가드 | python3 scripts/contract_guard.py check --target index PASS |

정답 승인, P021 완료 및 P013의 모델/예산·인터페이스 등 미결 준비 게이트는 이 검토로 닫히지 않는다. READY로 전환하거나 dev에 착수를 지시하지 않는다. 후속 구현은 P013 준비 완료 검토와 정확한 계획 채택 이후다.

기존 미커밋 architecture/P014/roadmap/project-brief 변경은 이번 커밋에 포함하지 않는다. 이 변경의 전달 대상은 공개 저장소 milkpotato1000/hr_rag의 plan 브랜치이며 dev 구현·main 승격은 범위 밖이다.
