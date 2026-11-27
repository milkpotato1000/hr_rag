# P032 S1 legacy buffer 후속 준비 검토 — 2026-11-28

READY. 사용자 최종 RAG 모델 선택·실사용 비교 goal과 plan 준비 검토·직접 dev 전달 위임 안의 호환성 수정이다. 실제 모델 변경이나 평가기 재개가 아니다. [후속 계약](../specs/P032-s1-legacy-buffer-contract.md)의 정확 채택 이후에만 구현·검증·남은 실행을 허용한다.

## 문제와 증거

기존 S1 채택57afafb, 구현/동결 입력a294d28, 출력 경로 복구c1ea2f8의 이력을 확인했다. E5 다운로드/준비·smoke3·본21worker가 완료됐고 같은 source/chunk identity에서 BM25/E5 Dense/E5 Hybrid30건을 직접 읽었다. 전달 문맥 fact는24/38,27/38,27/38이며 생성0이다. mMiniLM은 정상 파일 준비 뒤 첫20pair 시도에서 model_weights_mismatch로 중단했고 worker가 종료됐다. ledger의 실패·예약·처리량 불명 null을 성공으로 바꾸지 않는다.

실제 mMiniLM 고정 revision1427fd652930e4ba29e8149678df786c240d8825의 safetensors header와 position_ids의 작은 원본 bytes를 읽었다. I64[1,514]이며514개의 값이 arange(514)와 같다. 설치 transformers5.24.1 소스는 이 buffer를 persistent=False로 재생성한다. 저장/loaded persistent key 집합을 그대로 비교하면 이 buffer 때문에 정상 구형 파일도 거부될 수 있다. 다만 이전 응답이 전체 diff를 보관하지 않았으므로 이것이 유일한 차이라는 것은 후속 실제 검증에서 입증해야 한다.

## 허용 결정

예외는 정확한 모델 ID/revision과 `roberta.embeddings.position_ids` 하나다. 동일 이름이 nontrainable buffer인지, 원본과 재생성된 dtype/shape/value가 모두 결정 규칙에 맞는지 확인한 경우만 persistent 비교에서 별도로 처리한다. 나머지 key/shape/classifier/num_labels/raw logits/token·원본 hash 검사는 유지한다. `position_embeddings.weight`, 다른 key, 다른 revision, BGE 모델에는 포괄 예외를 주지 않는다. 요청에 언급된 두 reranker 전체 허용보다 현재 실제 증거가 있는 범위로 한정한다.

부족한/추가된/다른 shape의 학습 가중치까지 허용하는 수정이 아니며, 기존 stored==actual을 무조건 꺼서 통과시키지 않는다. 독립 tiny 정상/변조 시험과 locked SDK buffer 재생성 증거, 현재134개 회귀·설치 검증을 먼저 요구한다. 실제 후속 첫 smoke에서 다른 diff가 발견되면 실패와 중단을 유지한다.

## 누적 실행 경계

첫 실패를 포함한 reranker smoke5worker/100pairs, 전체73worker/500pairs로 한 번 개정한다. 기존 예약25worker와20pair 시도를 계승하며 남은48worker 이내다. E5 성공 결과를 다시 실행하지 않는다. mMiniLM/E5 다운로드 추가0, 미실행 BGE 두 모델은 원래 승인된 최초 준비 각1회다. 한도는 모델 작업의 누적 실행량이며 실제 처리 완료 수와 별도로 기록한다.

최초 시작1795801676.159772, deadline1795808876.159772는 불변이다. 코드/시험에 시간이 걸려 deadline을 넘기면 이 계약으로 추가 실제 호출을 하지 않는다. worker300초·RSS4GiB·normal pressure·단일 owned worker·실패 시 종료 기준은 유지한다. parent halted ledger/manifest·실패·모든 산출물은 보존하고 별도 continuation에서 최초 시간·기존 시도·새 채택/설치/runner identity를 연결한다. 이 명시 후속 계약 없이 기존 중지를 자동 해제하는 기능은 만들지 않는다.

S2/S3와 사용자 생성 profile/Drive 링크 대기, P013/P014·grant·P029 C4 보류를 유지한다. 실제 LLM/API/Ollama 제어·평가기0이다. 현재 dev의 결과 보고/UI 검증 작업을 먼저 보존·커밋하고 이후 후속 READY를 채택한다. 변경된 완료 조건으로 실패를 삭제하지 않으며 P032 전체 완료를 선언하지 않는다.

dev 요청 R20261127-94452f98은 커밋dfc3e18에서 확인했고 request SHA2567ae8a32faa8faa354db61aa49beca9340dacdecdf12614a355483654cd3d9913으로 P032에 연결했다. 요청 연결 자체가 실행 허가는 아니며 실제 READY 커밋·정확 채택과 후속 계약이 실행 범위다.
