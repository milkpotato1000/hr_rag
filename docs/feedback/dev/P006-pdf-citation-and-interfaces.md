# P006 실제 인터페이스와 PDF 인용 한계

채택 plan: 954245576a55ff99d4da98f233332b9e3769c096. 구현은 `1. Naive RAG/`에 있다. 이 파일은 plan이 후속 P007/P008 계약에 사용할 dev 피드백이며 다른 채팅에 메시지를 보내지 않는다.

- 수집: `scripts/snapshot_drive_fixture.py --catalog ... --output-dir ...`. network 없는 fixture 전용 어댑터. snapshot manifest에 stable file_id, 합성 원격 메타데이터, 실제 cache byte hash 기록. source_mode=live 거부.
- 추출: `scripts/ingest_documents.py --manifest ... --output-dir ...`. 완료 manifest와 검토 필요 review.json 분리. canonical text + 페이지별 raw/normalized 텍스트 + page map.
- 청킹: `scripts/chunk_documents.py --documents <추출 manifest> --method fixed --size-chars 400 --overlap-chars 80 --output-dir ...`. chunks.jsonl/source-map.json/manifest.json. 같은 콘텐츠·설정은 같은 실행 ID, 시간 포함 artifact hash는 별도 metadata.
- 평가 준비: `scripts/prepare_source_evaluation.py`와 data/source-v2/evaluation/source-evaluation.json. 15 facts / 29 required spans / 14 questions. 원문 span은 Unicode code point [start,end), 여러 필수 span을 하나의 fact에 허용. P007의 qrels/coverage/macro 산식은 아직 채택하지 않았음.
- 실제 산출물: 6문서, 8개 페이지 단위(PDF 4 + MD 4), canonical 5669자, 20청크, 3개 페이지 경계 청크. 현재 각 개별 fact는 하나의 청크가 모두 포함할 수 있으며 복수 청크 필수 fact는 독립 fixture로 구조 검증. q03 등 여러 facts 질문은 여러 위치 근거가 필요.
- RAG: 기존 rag.ask의 chunks_path를 재사용하고 ask.py에 --chunks 추가. 별도 색인은 .runtime/index-source-v2-fixed-400-80. 기존 15청크/index-v1/UI 기본값/프롬프트/모델은 보존.
- 실측 한계: q06은 검색 성공·내용상 맞는 초안이지만 모델 quote가 PDF 줄바꿈을 생략하여 기존 exact substring 검증 실패. docs/verification/p006/live/q06.json 및 review.md 참조. q04 의미 동등 smoke는 정확 인용 answered, q13은 적절 보류.

P007에서 단순히 top-k Recall만 보면 인용 실패를 놓칠 수 있다. P008 답변 평가는 답변 내용/인용 형식/최종 보류 사유를 나누고 원문 증거를 함께 비교해야 한다. PDF 줄바꿈 정규화나 인용 검증 규칙 변경은 이번에 수행하지 않았다. 변경한다면 원문 offset 추적과 기존 회귀 영향을 명시할 계약이 필요하다. 실제 Drive 연결은 별도 지정 폴더, 다운로드/네이티브 export, 권한·삭제·재색인 정책이 준비된 뒤에만 활성화한다.
