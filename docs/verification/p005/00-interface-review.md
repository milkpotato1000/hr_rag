# P005 착수 검토

P004 완료 커밋 38d276ef994ac89196fbd2620c0fe26d694050c1 및 personal/dev 일치를 확인한 뒤 plan 863a574b26535f80418b54e2f3204024e6e97fa8을 채택했다.
P004의 rag.ask(question, retriever, top_k, index_dir, max_context_chars, timeout_seconds)는 그대로 UI/API에서 재사용할 수 있다.
결과 status/answer/citations/reason/trace가 P005 계약과 일치한다. trace의 error.kind는 input/provider/timeout/execution이며 HTTP400/502/504/500으로 매핑한다.
후보에는 원문·출처가 있고 contexts/excluded 및 prompt/generation/timings가 분리되어 있어 중복 로직 없이 렌더링한다.
P004 총68 PASS, root19, standalone68 및 실제 q10 정상/q13 보류를 확인했다. 첫/두 번째14질문 및 Codex 의미 검토와 실패 로그를 보존했다.
실제 답 가능11질문 중 정확5/부분2/과도보류4이며 이를 제품 품질의 한계로 공개한다. q01 실패를 정상 답변으로 포장하지 않는다.
계약은 모든 질문 정답을 요구하지 않으며 실제 정상·보류 smoke가 있다. UI의 기본 예시에 q01/q03/q13과 q10 정상 사례를 함께 둔다.
P004 결과와 P005 인터페이스 사이 불일치는 없으므로 순차 착수한다. main/배포/외부 계정/새 RAG 방식은 범위 밖이다.
