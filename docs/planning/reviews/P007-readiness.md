# P007 준비 검토 — source-v4 장문 규정집 완료 대기

2026-10-29 갱신 판정: **DRAFT 유지**. P015가 미착수였던 이전 확인은 완료 commit `7980162d9204d0443235f4dabaa835c0d19a39fc`로 대체한다. 사용자 요청 R20261029-593e4840에 따라 [P016](../plans/P016.md)의 장문 source-v4를 실험 입력으로 사용한다. source-v3의 짧은 원문으로 P007 실행 조건을 먼저 확정하지 않는다.

## 확인한 현재 상태

- dev `1c0e861a0aaa63256896b0b99897ec0553a379a4`에서 새 요구를 접수했고 P015는5/5 완료다. P015 PDF6개/6페이지, canonical192~469자, 조항19개, 테스트229개 PASS 기록을 확인했다. [P016 입력 근거](P016-baseline.json)는 인계46파일 hash도 완료 commit과 대조한다.
- `2. Document Chunking/`와 source-v3는 존재한다. source-v4는 새 구현 대상이다. 기존 원문/완료 증거를 보존하며 새 원문은 길이·계층·참조·정책 검증을 거친 후 고정한다.
- 이전 [기존 코드 확인 목록](P007-source-inventory.json)은 dev `d3d16fe29fe4fa384b75a700940d11e33007ea51` 시점의 조사다. 최종 복사 manifest로 쓰지 않고 최신 P015/P016 도구와 import closure를 재대조한다.

## 유지하는 설계와 재검토 대상

[상세 계약](../../architecture/chunking-experiment-contract.md)과 [초기 실험 spec](../specs/P007-experiment-draft.json)의 다섯 방식·원문 slice/coverage·fact/span 평가·같은 corpus/검색 입력·query-independent LLM·원문/청크/검색 UI 원칙은 유지한다. title path는 메타데이터로 보존하며 긴 조항은 내부에서 재분할한다. 기본 비교의 title enrichment 제외 원칙도 유지한다.

14설정은 후보이며 source-v4 길이/구조로 다시 검토한다. 과거 문서당8window·300요청/120분은 실행 한도가 아니다. 14기존 tuning+12holdout·440/1320ranking도 규모 예시로만 보존한다. 최종값은 spec에서 null이며 source-v4 프로파일, 신규 정책/절차·조건부 예외/다중 조항을 포함한 질문 구성, 모델 입력 한도/호환·자원 검증으로 확정한다. 그 전 모델 실행이나 문서 절단을 허용하지 않는다.

## READY 전 남은 확인

| 항목 | 현재 | 완료 근거 |
| --- | --- | --- |
| P016 원문/추출 | P016 준비 완료, 산출물 대기 | 완료 commit,6문서/PDF/canonical/page/section/policy map·hash·전 페이지 검수 |
| 실제 단위/계층 | source-v4 미확정 | 문서/조항/문단 길이·정확 heading 위치/제목 경로·unit/window 수·페이지 경계 |
| 검색 정답/질문 | source-v4로 재준비 | 기존14개 재대조·추가 가상 정책/예외/참조 질문·새 tuning/holdout 크기/동결 hash; 과거 offset 미사용 |
| 모델/입력 한도 | 기존 lock 후보 | 설치 digest/version·옵션/schema smoke·tokenizer/template 또는 검증 가능한 입력 상한 |
| 자원/실행량 | 과거 예산 무효 | 전체 source-v4 coverage를 전제로 window 합계·3반복/재시도·smoke·시간·벡터/검색량·ledger 최종 제한 |
| 복사/UI | 과거 코드 목록 | 최신 도구/공용 의존성·copy hash·PDF 미리보기,장문 페이지 탐색/긴 목록·진행/실패·390/1200px 검증 계획 |

P016 완료 후 plan이 위 항목을 채워 계약/spec을 확정하고 준비 완료로 커밋·등록한다. 준비용 모델 smoke가 필요하면 좁은 사전 검증 범위/예산을 먼저 명시한다. 초안의 과거300요청 예산을 사용하지 않는다. 실제 준비가 갖춰졌다면 추가 인계 결재를 반복하지 않는다.

## 검증과 한계

이번 갱신은 선행/입력 버전·실행 예산 준비 상태 변경이다. P015 체크/실행 로그나 제품 원문은 수정하지 않는다. P007 초안·미착수·빈 실행 로그 및 새 선행 P016, JSON/링크/큐를 검사하며 PDF·청킹·모델·UI 제품 테스트를 수행했다고 주장하지 않는다. 역사적 상세 설계 및 후보 값은 Git 이전 commit에서 확인할 수 있다.
