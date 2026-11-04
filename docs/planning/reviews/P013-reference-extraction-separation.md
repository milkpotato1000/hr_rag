# P013 정답 후보 작성 / 추출 검증 분리 검토

날짜: 2026-11-04. 사용자 결정: 정답 후보는 Codex가 원문 기반으로 만들고 사람이 승인한다. Qwen의 Claim Extraction 성능은 고정 답변으로 따로 검증한다.

## 반영 범위

- [P013](../plans/P013.md) C1에 Codex 원문 기반 후보·사람 승인을 명시하고 Qwen 정답 생성의 필수 의존을 제거한다.
- C2에 고정 답변·사람 검토 기대값으로 Qwen 추출 단독 검증을 추가한다. [별도 검증 초안](../specs/P013-claim-extraction-validation-draft.md)에 입력/기대값 분리·비유출·동결/실행 순서·필수6유형·오류 보존·추출 P/R/F1·0분모/실패 정책을 기술한다.
- [상세 준비 초안](../specs/P013-evaluation-draft.md)의 작업 순서·artifact 경계·사람 검토·READY 준비 항목과 [아키텍처](../../architecture/project-b-generation-evaluation.md)의 후보 작성자/모델 역할을 일치시킨다.
- 정답 후보 작성자는 Codex이고 실제 승인자는 사람이다. Qwen의 현재 생성/검증/매칭 역할은 이번 요청으로 교체하지 않는다.

## 이력과 권한

P019/P021의 기존 Qwen 초안·Codex 수정·원응답·패킷 hash를 보존한다. 재사용하려면 새 버전에 원문 재확인·유지/수정 사유·이전 ID 대응을 남기고 실제 사람이 승인해야 한다. 현재 검토 자료를 자동 승인하거나 작성 이력을 소급 변경하지 않는다. 고정 답변의 기대 클레임은 답변의 사실 오류까지 충실히 보존하는 별도 라벨이다.

이번 작업은 계획 변경이며 제품 구현·정답 패킷 재작성·Qwen 실행은0회다. P013은 DRAFT/미착수·0/4, 실제 정답 승인과 P021 완료 및 준비 게이트는 유지한다. READY나 착수 메시지를 만들지 않는다. 공개 저장소 milkpotato1000/hr_rag의 plan 브랜치에만 반영한다.

기존 미커밋 architecture의 Jev/CDM 학습 확장, roadmap/P014/project-brief 변경은 별도 미커밋 작업으로 보존한다. architecture는 이번 역할 분리 부분만 선택적으로 커밋한다.

## 계획 검증

정답 작성·추출 입력·기대값·사람 검토 주체의 문서 간 일치, 기존 세 근거 비율 요구/18개 산술 fixture 보존, 카드 상태와 필수6유형·실패/0분모 정책·상대 링크를 검사한다. P/R/F1 산술 재확인은 계획 기대값의 확인이며 모델 정확도 검증이 아니다. 준비 검토 시 실제 세트·검토자 증거·실행/통과 기준과 예산을 동결해야 한다.

- PASS: 문서 역할/입력 분리, 필수6유형과 추출 P/R/F1·무주장/실패 정책, 상대 파일 링크 일치.
- PASS: 추출 H/A/B=(2,3,4)에서 P=2/3, R=1/2, F1=4/7. 무추출/무기대값/둘 다0인 산술 경계도 명시 정책과 일치.
- PASS: 기존18개 산술 fixture 바이트 동일, Neutral·Contradiction rate와 Correctness 요구 보존, P013 초안/미착수·0/4 유지.
- PASS: 기존 별도 변경 파일 hash 보존, architecture 역할 분리 부분만 선택 staging.
- PASS: git diff --check 및 python3 scripts/contract_guard.py check --target index.
