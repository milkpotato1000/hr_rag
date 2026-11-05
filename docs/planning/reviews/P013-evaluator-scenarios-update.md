# P013 근거·답변 누락 상황별 검증 추가 검토

날짜: 2026-11-05. 사용자 요청: “P013에도 생일휴가 예시처럼 근거 청크가 모두 있는 경우, 일부 빠진 경우, 답변에서 클레임이 누락된 경우를 나눠서 평가기를 검증하도록 반영해줘.”

## 변경 결정

동일 질문과 정답3개를 고정하고 근거/답변 전체 또는 일부의2×2 네 상황으로 기존 P013 C2/C3를 구체화한다. [P카드](../plans/P013.md), [상세 준비 초안](../specs/P013-evaluation-draft.md), [상황별 계약](../specs/P013-evaluator-scenarios-draft.md), [고정 입력/기대값](../specs/P013-evaluator-scenarios-draft.json)을 연결한다.

| 상황 | Faithfulness / Neutral / Contradiction | Correctness P / R / F1 |
| --- | --- | --- |
| A 전체 근거·전체 답변 | 1 / 0 / 0 | 1 / 1 / 1 |
| B 근거만 누락 | 2/3 / 1/3 / 0 | 1 / 1 / 1 |
| C 답변만 누락 | 1 / 0 / 0 | 1 / 2/3 / 4/5 |
| D 근거·답변 누락 | 1 / 0 / 0 | 1 / 2/3 / 4/5 |

근거가 없는 주장과 생성하지 않은 정답 주장을 구분한다. matcher에는 전체 ref1~ref3를 유지하고 verifier에는 실제 전달 snapshot에 해당하는 ctx만 제공한다. B의 g3는 정상 neutral이며, C/D의 ref3는 FN1이다. 누락 청크를 평가 때 보충하거나 누락된 답변 클레임을 추출 결과로 만들어내면 실패다.

## 범위·한계

세 사실만 존재하는 합성 테스트 정책이며 실제 HR 규정집/수습 조건/정답 패킷을 바꾸지 않는다. fixture는 synthetic=true, human_approval=null이다. 고정 답변에서의 Qwen 추출 검증, 고정 claims로 평가기 판정/매칭을 대조하는 검증, 실제 검색·생성 E2E를 분리한다. 기대 라벨과 산술 계산 확인은 실제 모델 정확도 PASS가 아니다.

현재 정답 미승인, P021 미완료와 P013 READY 미결 게이트·0/4 체크를 유지한다. 계획 변경·합성 기대값 작성만 수행하고 모델/검색/생성 실행과 dev 착수 메시지는 만들지 않는다. 기존18개 산술 fixture와 고정 답변 추출 검증 계약을 보존하며 공개 저장소 milkpotato1000/hr_rag의 plan 브랜치에만 반영한다. 기존 미커밋 네 문서는 포함하지 않는다.

## 검증 범위

모든 경우의 전달 청크/생성 claim/전체 reference ID, 입력 hash, claim별 라벨·근거 ID, 일대일 매칭·미매칭 ID, 독립 Fraction 기반 산술, A↔B/A↔C/B↔D의 입력 통제, 문서/JSON 기대값·상대 링크, 기존 fixture·문서 상태 보존을 검사한다. 실제 사람 라벨과 모델 실험의 실행·통과 기준은 P013 준비 검토에서 고정한다.

검사 결과:

- PASS: A/B/C/D의 기대 라벨·근거 ID·매칭·미매칭 ID·비율과 P/R/F1을 Fraction 산술로 재계산해 일치 확인.
- PASS: A↔B 답변 고정, A↔C 문맥 고정, B↔D 문맥 고정, 각 상황 전체 GT3개 유지 및 입력 hash 재계산.
- PASS: 상대 링크, P013 초안·미착수·0/4, 기존18개 산술 fixture/추출 단독 계약 바이트 동일, 기존 미커밋 네 파일 hash 보존.
- PASS: git diff --check. 실제 검색·생성·Qwen/NLI 호출0회이며 이 결과는 모델 판정 정확도 PASS가 아님.
- PASS: python3 scripts/contract_guard.py check --target index. 리랭킹 사용 여부는 기존 단계 계약을 따르며 P013에 새 리랭커를 요구하지 않음.
