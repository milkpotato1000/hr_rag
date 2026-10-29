# P007 준비 검토 — 단일 규정집 청킹/검색 실험 준비 완료

2026-10-29 사용자 “P016 단일 규정집 작성 진행 상황 확인, 끝났으면 P007 청킹 실험 준비 이어서 진행” 요청에 따라 **준비 완료·dev 등록**으로 전환한다. P016 완료 확인과 계획 범위 안의 제한된 사전 검증을 수행했다. P007 제품 구현·전체 청킹/검색 실험·UI는 아직 미착수이며 dev의 정확한 plan 통합/채택 후 진행한다. 추가 결재나 다른 채팅으로 자동 시작 메시지를 요구하지 않는다.

## 입력 검토

P016 완료 commit `4cdee6f9583c899d76e95237af8b5de8d77d8012`의 카드5/5·완료 증거를 확인했다. 단일 Markdown/PDF23페이지, 본문35,477자/canonical38,582자·6장15절57조항이다. P016의27테스트/전 페이지 직접 검수/정책31개 보존/독립 재현 PASS는 커밋된 기록을 검토한 것이며 이번 plan이 PDF를 다시 검수하거나 전체 제품 테스트를 재실행했다는 의미가 아니다.

[source profile](p007/source-profile.json)을 생성하며 인계62파일 및 완료증거10파일 hash와 section map의 정확 heading/body/extent quote를 재검산했다. canonical SHA는 `1c6867d284d136b2eb1cf6f9a707506480946988eaa155ae46b13ce25e2eb298`, 인계 manifest SHA는 `82918298ce6abeab89c033ab055fcba12302069a27ba0bc7f413bd98d783888a`다. section/corpus hash는 spec에 함께 고정했다. 원문과 dev 파일을 변경하지 않았다.

## 고정한 실행 계약

| 항목 | 준비 근거와 기준 |
| --- | --- |
| 원문/단위 | 단일 document_id·연속offset·실제 제목79개, 경계 단위630개/강제400자 분할0; [경계 map](p007/boundary-map.json)과 독립 fixture 재현 |
| 청킹 | fixed6 + recursive2 + structure2 + semantic2 + LLM2 =14설정. 실제 제목/장/절/조항 경계·긴 구간 재귀 분할, 메타데이터 제목 경로 보존, 기본 검색 입력은 text-only |
| 검색 정답 | [dataset](../specs/P007-retrieval-dataset.json)의37fact/38질문: tuning26(기존14+신규12),holdout12(가능10/불가2),신규 질문군 조항 중복 없음·장 간 복수 근거 포함 |
| 근거 계산 | fact별 OR evidence_sets·각 집합 내부 AND spans,질문은 필수fact 모두. 등록 위치 기반 회수 지표이며 모든 의미상 동등 표현을 완전하게 주석한 세트는 아님 |
| 입력/모델 | 기존 Ollama0.40.8·Qwen3:4b/BGE digest 일치, 단일 user prompt/schema 고정,1200자/20단위×35window. 최대 보수적 입력6510+출력1024 < context8192 |
| LLM 호출 | 전체3반복=105회,각window 최대2시도로210회+준비3+dev smoke6=219회 상한; 요청90초/전체120분. 준비 호출을 ledger에 포함 |
| 임베딩/검색 | 준비2item 포함총32000item/30분,배치32·동일item 최대2시도; query ranking776개,지연3회 포함최대2328개 |
| UI/복사 | 기존후보 정적28파일 [copy candidates](p007/copy-candidates.json),새 단계 충돌파일 보존·통합. PDF23장 [preview manifest](p007/preview-manifest.json) hash 확인; 통합목차/장·절/페이지/원문·청크·검색,8003 |

## 제한된 실제 환경 검증

[사전 검증 범위](p007/preflight-scope.md)에 먼저 예산을 명시하고 기존 localhost 모델만 확인했다. [runtime metadata](p007/runtime-metadata.json), [prompt contract](p007/prompt-contract.json), [probe 요청](p007/probe-requests.json), [probe 결과](p007/probe-results.json)를 보존한다.

- Qwen 경계 선택3회: JSON·ID존재/순서/중복·마지막ID·전체window coverage·최대800자 모두PASS. w012를 두 번 별도 호출했고 경계는 일치했다. 두 개 window 표본이며 전체35window·3반복 안정성 검증을 대신하지 않는다. 실제 소요19.26/16.14/9.17초,관측입력1578/1492/1578토큰이다.
- **세 probe 모두 모든 단위 끝을 선택했다.** 형식/실행 호환은 확인됐지만 주제 묶음 품질이 좋다는 증거는 아니다. 권장200~400자는 강제가 아니며 실제 짧은 청크 비율/단위 수 대비 청크 수를 실험에서 보고한다. 편의상 병합하거나 fixed fallback으로 숨기지 않는다.
- BGE1요청/2입력: truncate=false·유한1024차원/0이 아닌 벡터 PASS. 문서 전체 semantic 분할/색인/검색 품질은 미실행이다.
- Python3.12.14,langchain-core1.7.0,langsmith0.14.14,qdrant-client1.19.1,pdftoppm26.08.0을 확인했다. 호스트 총메모리는16GiB이며 가용/peak 메모리를 보장하지 않는다. 제품 구현 시 peak/지연·실패를 별도 기록한다.

## 입력 한도 실패와 수정 근거

최초1600자/24단위 후보는 입력 보수 상한7836+출력1024로8192를 초과했다. 이 상태로 모델을 호출하지 않고 [실패 기록](p007/input-budget-first-failure.json)을 보존한 후1200자/20단위로 변경했다. 원문 coverage는 그대로이며 window27개가35개가 됐다. 35개 전부의 [현재 입력 상한](p007/input-budget.json)을 확인한 뒤만 probe했다.

byte-BPE의 UTF8 byte 수 상한을 사용하며 단일user/no system/tools/images/history·현재template에 한정한다. 전체template 바이트와 schema 중복분·special framing64를 여유로 포함했다. 이는 정확 tokenizer count가 아니며 API 관측 token 수만으로 무절단을 증명한 것도 아니다. 메시지 형태·모델·template/버전 변경 시 상한을 재검토한다. JSON/schema와 모든 원문을 포함한 실제 content 바이트를 매 요청 검사한다.

## 인계·검증 경계

[P007](../plans/P007.md)·[상세 계약](../../architecture/chunking-experiment-contract.md)·[고정 spec](../specs/P007-experiment-draft.json)을 함께 채택한다. spec 파일명의 draft는 기존 참조 경로이고 현재 status는 READY_FOR_DEV_ADOPTION이다. plan 준비 artifact는 입력/규격/검증용이며 제품 구현의 복사본으로 가장하지 않는다. dev는 독립 fixture와 실제5방식/검색/UI/E2E를 완성해야 한다.

PDF 미리보기는 P016 검증PNG23장을 새 단계 previews/source-v4/에 출처/hash와 함께 복사하는 방식이므로 런타임 renderer나 상위 docs 폴더 의존이 없다. 재렌더링하는 경우 새 hash/시각 검수를 수행한다. 기존2단계 document_common.py/test_documents.py는 후보와 달라 덮어쓰지 않고 기존27테스트/추출 동작을 보존한다. 원래 Naive·source-v3/v4는 변경하지 않으며8001을 유지하고 종료된8000을 자동 재시작하지 않는다.

준비 확인은 JSON·연결·합계/호출 예산·원문 exact span·출처 hash·기존 완료 카드 무변경·빈 P007 실행 로그·큐/훅이다. [요약](p007/readiness-summary.json)에 실제 수행과 한계를 기록한다. 자료 부족/새 의미 결정은 현재 없으며 실행 오류는 완료 조건을 축소하지 않고 실패·수정·재검증으로 다룬다. 사용자에게 문서/코드 구현을 넘기지 않는다.
