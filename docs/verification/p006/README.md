# P006 원문 수집·추출·청킹 기준선 검증

채택 plan: `954245576a55ff99d4da98f233332b9e3769c096`. P005 완료 및 사용자 연차 문구 정정이 포함된 dev `8d150f44251919f9326cb22778d0b8bcae72dae7`를 보존했다. 최초 e3dc0cb 채택 후 Drive 추가 계약을 기존 로그/작성물을 보존해 재채택했고 완료 체크를 자동 승계하지 않았다.

## 결과와 검증 근거

| 조건 | 결과 | 근거 |
| --- | --- | --- |
| C1 원문/Drive fixture/추출 | PASS | 새 원문 6개, 대표 입력 PDF 2개(각 2페이지)+MD 4개. snapshot byte 동일·ID/이름/내용 변경·페이지 분류 테스트, 04-source-audit.json, pdf-render 4페이지 직접 확인 |
| C2 fixed 청킹/출처/재현 | PASS | 400/80 기준 20청크·페이지 경계 3청크. 독립 경계/Unicode/공백/원자적 출력 race·반복 ID/hash 및 source-map 검사. 05-delivery/stage-tests-stderr.txt, copy-summary.json |
| C3 실제 검색/생성 연결 | PASS, 품질 한계 보존 | 실제 새 BGE 색인 20개(03-index-build.json), 정상 PDF q04와 적절 보류 q13, live/stale-index-rejection.json 및 bm25-new-corpus.json. q06 인용 줄바꿈 실패는 live/review.md에 유지 |
| C4 원문 평가 준비 | PASS | 15 facts/29 spans/14 questions, exact canonical quote·page/hash/provenance 역추적, 기존 qrels 미복사, 런타임 입력 read spy. source-v2/evaluation/source-evaluation.json, 04-source-audit.json |
| C5 회귀/복사/학습 | PASS | stage 96, root 19, source-only copy 96. 복사한 원문부터 snapshot→추출→청킹→평가→새 실제 색인→Qwen q04/q13까지 재현. 05-delivery/commands.json 및 copy-summary.json |
| C6 채택/보존/훅 | PASS | 정확한 plan 채택, P005 선행, 185개 기존 파일 byte 보존, 계약/큐/staged diff 검사와 커밋 훅. 07-final-checks.txt 및 이 완료 커밋 |

96개 stage 검증은 기존 76개와 신규 20개다. 자동 테스트는 기능/계약 경계를 검증하며 답변 의미 품질을 일반화하는 점수가 아니다. 단독 복사는 기존 고정 interpreter·소유 loopback 모델을 사용하고 source·코드만 복사했다. 모델 재다운로드 없이 별도 색인을 실제 재구축했으며 원문/청크/source map/평가 바이트와 run ID가 동일했다.

## PDF 직접 확인

`pdf-render/birthday-1.png`, `birthday-2.png`, `annual-1.png`, `annual-2.png`를 모두 열어 한글 glyph, 숫자/부정 표현, 제목·문단·목록·페이지 번호, 여백을 확인했다. 잘림/겹침/깨진 글자는 관찰되지 않았다. birthday는 첫 페이지의 확인 순서 문장이 다음 페이지로 이어진다. 연차의 “5일분”, “3월 31일”, “0.5일”, 생일 특별휴가 제외/분할 금지, 각 신청 기한은 추출 텍스트와도 대조했다.

기존 15개 정책 본문은 공백을 제외한 전체 내용으로 새 canonical 문서에서 확인했다. 이 비교는 정책 보존 검사이며 검색 점수나 답변 의미 자동 채점이 아니다. 원문/PDF는 이번에 새로 작성했고 과거 원본이었다고 주장하지 않는다.

PDF 줄바꿈과 바닥글/페이지 번호는 그대로 추출한다. 규정 문장 사이에 페이지 표기가 들어갈 수 있고 일반 표/다단 순서를 복원하지 않는다. 이미지 존재+텍스트 없음은 OCR 후보, 둘 다 없음은 빈 페이지 후보이며 vector 글자 등의 자동 판단 한계가 있다. 해당 페이지는 review.json으로 기록하고 완료 manifest/청킹을 막는다. 암호화·손상·파일/페이지/문자 제한·실제 subprocess timeout과 기존 결과 보존도 검증했다.

## 최초 실패와 처리

1. `01-first-tests.txt`: 94개 중 반복 전체 파이프라인의 청킹 run_id 1개 실패. 추출 manifest의 elapsed_ms가 포함된 artifact hash를 run identity에 넣은 원인이었다. 콘텐츠에 근거한 ingestion_run_id를 identity에 유지하고 시간 포함 artifact hash는 별도 관측 metadata로 옮겼다. `02-recheck-tests.txt` 94 PASS, 두 경계 테스트 추가 후 최종 96 PASS. 최초 chunk manifest는 first-chunk-manifest.json에 보존.
2. `live/q06.json`: 근거가 검색 1위이고 답변 초안은 수량·기한을 올바르게 설명했지만 두 인용이 PDF 줄바꿈을 제거해 exact substring 검증 실패. 최종 과도 보류로 분류. 규칙/문서/프롬프트를 바꾸지 않았다. 계약의 최소 정상 답변/적절 보류는 q04/q13 및 별도 복사 E2E로 확인했다. q04 첫 실행은 의미 동등 문장, 복사 재현에서는 기존 q04 질문 원문을 사용했다. 전체 14개 답변 품질을 측정했다고 주장하지 않는다.
3. `06-first-whitespace-check.json`: diff 검사에서 추출 텍스트의 trailing space를 지적했다. 원문 데이터의 의미/offset/hash를 보존하기 위해 해당 extracted/**/*.txt만 `.gitattributes`에서 byte 보존 및 blank-at-eol 허용으로 지정했다. diff 자체, 다른 공백 검사, 코드/설명 문서, 계약 훅은 계속 검사한다. 오류 출력은 JSON 문자열로 lossless 보존했다.

## 경계와 인계

실제 Google Drive 연결/다운로드/업로드/동기화는 하지 않았다. 모든 원격 ID는 fixture 접두어이고 URL/수집 시각은 null, 수정 시각은 합성임을 명시한다. 로컬 cache 사본과 stable file_id의 역할을 분리했다. 실제 연결·Google Docs export·권한/삭제/활성 색인 전환은 후속 계약 대상이다.

기존 UI/server/rag 코어/모델/프롬프트와 15청크·질문·기존 증거는 보존했다. `ask.py --chunks`만 명시 선택 인자로 추가했고 새 색인은 `.runtime/index-source-v2-fixed-400-80`이다. UI는 기존 corpus를 사용하며 `/api/status` HTTP200과 소유 runtime 상태를 확인했다. 원문 corpus UI 전환은 P008 범위다.

새 청킹 방식·검색 지표 산식·tuning/holdout는 P007, 답변/UI 비교는 P008 초안이다. 이번에 실행하지 않았다. `docs/feedback/dev/P006-pdf-citation-and-interfaces.md`에 실제 인터페이스와 PDF 인용 한계를 남겼다. 사용자는 원문/경계/평가 의미를 관찰하며 설치·구현·테스트를 직접 수행하는 과제를 받지 않는다.
