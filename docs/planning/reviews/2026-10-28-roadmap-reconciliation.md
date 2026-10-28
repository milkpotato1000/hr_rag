# 2026-10-28 dev 로드맵 → plan 대조 기록

## 범위와 근거

사용자 요청: “지금 dev 에 작성한 로드맵 관련 내용 한번 확인하고, 플랜에 잘 반영해놔줘”. 이번 작업은 기존 계획의 정합성 보완이며 P010/P007/P008의 준비 완료 승격이나 구현 착수가 아니다.

검토 시작 시 plan은 `e3e3f340531063b83fbb3aabb1b59066e034339b`였다. 이 커밋에 이미 Naive → Hybrid → PDF/청킹 순서와 P010 초안이 반영되어 있어 중복 카드를 만들지 않았다. dev의 다음 커밋을 기준으로 학습 내용과 구현 상태를 대조했다.

- dev 기준: `2414508f6acc1e6f9b0c19e480300ce9b0dab7f9` (로컬 dev/personal/dev 일치).
- [학습 가이드](https://github.com/milkpotato1000/hr_rag/blob/2414508f6acc1e6f9b0c19e480300ce9b0dab7f9/1.%20Naive%20RAG/LEARNING_GUIDE.md): 현재 UI 15청크, P006 별도 corpus, Hybrid 다음 PDF/청킹 학습 순서.
- [현실적인 원문 피드백](https://github.com/milkpotato1000/hr_rag/blob/2414508f6acc1e6f9b0c19e480300ce9b0dab7f9/docs/feedback/dev/realistic-source-documents.md): 원문 구조·학습 해설 분리·제목 메타데이터·기존 규정 의미 보존·버전 경계.
- [P009 남은 의미 품질](https://github.com/milkpotato1000/hr_rag/blob/2414508f6acc1e6f9b0c19e480300ce9b0dab7f9/docs/feedback/dev/P009-id-citations-and-quality.md): 조건 누락·과도 보류·선택 인용의 주장 미지원.
- 같은 dev 커밋의 `docs/planning/plans/P006.md`, `P009.md` 실행 완료/PASS 기록과 `docs/verification/p006/README.md`, `docs/verification/p009/final-review.md`: 구현 완료와 품질 한계를 대조했다. 이전 P001~P005 완료는 작업 큐의 커밋된 진척으로 확인했다.

링크는 로컬 Git에서 읽은 동일 커밋 파일의 고정 참조다. 웹 링크 접근을 별도로 검증했다는 뜻은 아니다.

## 반영 결과

| dev 내용 / 발견한 불일치 | plan 반영 위치 |
| --- | --- |
| Naive → Hybrid → PDF/청킹; 단계 번호와 P번호는 별개 | [로드맵](../naive-rag-roadmap.md), [프로젝트 기획](../project-brief.md), [폴더 규칙](../../architecture/stage-layout.md) |
| 기존 로드맵에 P006 “다음 dev 작업”, P009 “등록” 문구가 현재 상태와 함께 남음 | 현재 상태 표로 정리: P001~P006/P009 완료, P010 다음 기획, P007/P008 후속 초안 |
| 현실적인 독립 원문 작성·정책 의미 보존·학습 해설 제외 | [P007](../plans/P007.md) 원문 준비 요구와 C1 보강 |
| 새 원문은 기존 canonical offset/qrels를 그대로 쓸 수 없음 | P007에서 동일 버전 fact/span 재검토·새 색인/정답 버전 고정 |
| 제목 없는 후속 청크·나뉜 예외·생일 포인트/휴가 혼동 | P007 관찰 사례와 로드맵 청킹 절에 반영 |
| corpus/UI 적용 시점과 제목 메타데이터의 인용 혼입 방지 | [P008](../plans/P008.md) 준비 항목 추가 |
| ID/원문 일치와 답변 의미 지지는 서로 다른 검사 | [P010](../plans/P010.md) 회귀 사례 및 로드맵 평가 구간 구분 |
| 검색기/원문/청킹 변경 효과가 섞일 수 있음 | P010 corpus 고정, P007 원문 개정과 청킹 비교 분리, P008 최종 답변 검증 |

기존 완료 카드 P001~P006/P009의 요구·체크·실행 로그는 변경하지 않았다. dev 구현/증거를 plan으로 병합하지 않았으며 dev 파일은 수정하지 않았다. 초안 P007의 원문 검증 조건만 보강했고 준비 상태는 유지했다.

## 검증과 다음 작업

- `python3 scripts/work_queue.py --owner all --brief`: plan 다음 P010, dev 실행 가능한 승인 작업 없음.
- `python3 scripts/contract_guard.py check`: plan 브랜치의 dev 채택 검사는 SKIP이며 PASS로 표시하지 않는다.
- `git diff --check` 및 변경한 기획 문서의 로컬 링크·선행 관계를 점검한다. 제품 코드는 변경하지 않아 제품 테스트를 재실행하지 않는다.
- 다음 계획 준비는 P010의 RRF/실패 처리·고정 corpus·평가·UI·복사 출처 계약이다. 이번 대조 작업은 그 상세 계약 검토를 대신하지 않는다.
