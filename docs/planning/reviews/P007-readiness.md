# P007 준비 검토 — 상세 설계 작성, 입력 확정 대기

2026-10-29 사용자 “진행해줘” 요청에 따라 이 plan 채팅에서 P007 상세 계획을 진행했다. 현재 판정은 **DRAFT 유지**다. 이유는 P015가 아직 미착수여서 원문 길이/해시·조항 map·정답·실제 window/실행량을 확인할 수 없기 때문이다. 사용자의 추가 허가를 반복해서 요구하는 게이트가 아니라 선행 산출물 확인 절차다.

## 확인한 현재 상태

- dev `d3d16fe29fe4fa384b75a700940d11e33007ea51`, 채택 plan `385701a2d7cce2ad9f62b96da9b64fc06fd505d3`. 양쪽 작업 트리 변경 없음, 큐 다음 plan=P007/dev=P015, 새 요구 대기0건.
- Git 루트와 실제 파일 목록에 `2. Document Chunking/`/P015 완료 증거가 없다. 기존 source-v2의 길이/해시를 source-v3 결과로 대체하지 않았다.
- 기존 모델/runtime lock 및 청킹·검색·서버를 읽었으며 원본 파일별 SHA-256은 [기존 코드 확인 목록](P007-source-inventory.json)에 기록했다. 이는 최종 복사 manifest가 아니다.
- fixed는 문자400/80·canonical slice·page/source map/atomic publish를 제공한다. BM25/Dense는 제목+본문을 검색 입력으로 사용한다. 새 비교에서는 모든 방식에 text-only를 공통 적용하고 새로운 색인 fingerprint를 사용하도록 명시했다.
- 기존 generation adapter는 답변용 schema/lock을 검증하므로 청킹용 별도 adapter/lock이 필요하다. 기존 코드/생성 모델 요청을 변경하지 않는다. UI는 loopback·Host/Origin·CSP·body 제한을 재사용하되 동기 답변 API를 async 청킹 job으로 가장하지 않는다.

## 이번에 구체화한 설계

[상세 계약](../../architecture/chunking-experiment-contract.md)과 [초기 실험 spec](../specs/P007-experiment-draft.json)을 작성했다.

- 다섯 방식의 공통 원문 경계/overlap 규칙과 14설정: fixed6 + recursive2 + structure2 + semantic2 + llm2.
- LLM은 원문 ID만 선택; Python 검증/원문 slice, 제한 window, JSON/ID/누락/길이·실패 처리, 3독립 반복·경계 Jaccard/일치율, 캐시와 fresh 분리.
- 기존 Qwen/BGE/Ollama lock 후보와 초기 호출/시간·벡터 item 예산을 기록했다. 이 설계로 모델을 실행하거나 새 모델을 내려받지 않았다.
- fact/span 합집합 회수율·전체 근거 성공·부분coverage, 전략별 grade/qrels·P/R/MRR/nDCG·N/A/분모, 같은 K/분량 비교, tuning/holdout/후보 선정 기준.
- 실제 코어를 쓰는 원문·청킹·검색 UI/API, typed 오류·단계별 job/잠금·재시작/재접속·artifact 다운로드·PDF 경로 제한·390/1200px/키보드 검증.
- P013/P008 인계와 완료 C1~C6의 실제 검증 묶음. 새로운 P번호/제품 단계는 만들지 않았다.

## READY 전 남은 확인

| 항목 | 현재 | 완료 근거 |
| --- | --- | --- |
| P015 원문/추출 | 없음 | 완료 commit,6문서/PDF/canonical/page map·policy-map·해시·시각 검증 |
| 실제 분할 단위/조항 | 미확정 | section map exact 위치·문서 길이·unit/window 수·14설정 적용 프로파일 |
| 검색 정답/질문 | 의미/구성만 설계 | source-v3 exact fact/span·기존14/새12질문·검토/동결 hash |
| 모델/입력 한도 | 기존 lock 후보만 확인 | 설치 digest/version·옵션/schema smoke·tokenizer/template 또는 검증 가능한 입력 상한 |
| 자원/시간 | 초기 상한만 제안 | 실제 크기·메모리·처리 예상·probe/전체 호출 ledger 계약과 확정 spec |
| 복사·PDF 미리보기 | 읽은 코드 목록만 확보 | P015와 통합할 최종 import closure·copy hash·렌더러 버전/재현 경로 |

P015 완료 후 plan이 근거를 채워 상세 계약/spec을 확정하고 준비 완료로 커밋·등록한다. 그전에는 DRAFT를 dev에서 구현하지 않는다. 준비용 모델 smoke가 필요하면 별도의 좁은 사전 검증 범위/예산을 plan에 명시한 뒤 수행하며, 초안의300요청 예산을 사용하지 않는다. 미결 정책 판단이 아니라면 추가 인계 결재를 반복하지 않는다.

## 이번 검증과 한계

계획 문서의 링크, JSON 형식/14설정·440/1320 ranking 상한 계산, 후보 모델 lock 일치, 선행 순환/누락, 기존 완료 카드 무변경, P007 초안/미착수 및 빈 실행 로그를 검사한다. PDF·청킹·모델·UI 제품 테스트는 수행하지 않았다. plan 브랜치 훅의 dev 계약 검사는 SKIP이므로 제품 검증 PASS로 주장하지 않는다.

Ollama 공식 chat/structured-output/embed 문서를 확인했고 링크는 상세 계약에 남겼다. 문서 확인은 현재 로컬 런타임의 기능 검증을 대체하지 않는다. 기존 P015/원본 소스·실행 상태를 수정하지 않았고 dev로 전환하거나 구현 시작 메시지를 보내지 않았다.
