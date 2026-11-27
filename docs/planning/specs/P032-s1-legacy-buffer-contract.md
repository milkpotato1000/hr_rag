# P032 S1 mMiniLM 위치 buffer 호환성 후속 계약

2026-11-28 READY. 이 후속 계약의 정확 SHA 채택·커밋 후 코드 수정·독립 시험·새 설치 검증을 수행하고, 모두 통과하면 아래 별도 continuation으로 남은 S1 실제 실행을 진행한다. 기존 halted run을 덮어쓰지 않는다. P013 평가기/메모리 recovery와 무관하다. 기존 S1 계약 중 buffer 비교 예외와 누적 smoke 한도만 이 문서가 우선하며 나머지는 유지한다.

## 실제 중단과 읽기 증거

run001은 E5 준비와 smoke3 worker, 본 검색21 worker를 완료했다. BM25/E5 Dense/E5 Hybrid 각10질문 결과가 저장됐고 생성0이다. mMiniLM의 공개 파일 준비는 성공했지만 첫20pair smoke worker가 model_weights_mismatch를 반환하여 ledger가 halted가 됐다. 해당 시도는 reranker_smoke1, 요청20pairs로 남고 성공/완료 pair로 바꾸지 않는다. worker는 종료됐고 sampling peak928579584bytes, OS pressure normal이었다. BGE 두 모델 준비·추론은 아직 하지 않았다.

plan은 원본 가중치를 모델로 로드하지 않고 safetensors header와 작은 buffer bytes, 설치 SDK 소스만 읽었다. 실제 mMiniLM revision1427fd652930e4ba29e8149678df786c240d8825의 파일에는202 tensors가 있고 non-weight/bias 항목은 `roberta.embeddings.position_ids` 하나다. dtype I64, shape[1,514], 값514개는 config.max_position_embeddings=514의 arange와 정확히 일치한다. config.model_type은 xlm-roberta다. 정렬 JSON header의 SHA256은7dff17d06a7a5f20b49cc764959acdd9fa9f647c6cc787358f95816eadc313a8이다.

설치된 transformers5.24.1의 `models/xlm_roberta/modeling_xlm_roberta.py`68행은 같은 position_ids를 `nn.Buffer(torch.arange(config.max_position_embeddings).expand((1, -1)), persistent=False)`로 만든다. 기존 reranker_worker는 저장 tensor key/shape 전체와 loaded model.state_dict 전체의 완전 동일성을 요구한다. 따라서 이 비영속 buffer가 불일치의 유력한 원인이다. 아직 실제 loaded/stored 전체 diff를 수집하지 않았으므로 다른 불일치가 전혀 없다고 단정하지 않는다.

## 수정의 엄격한 범위

- 지원 예외는 위 고정 mMiniLM 모델 ID/revision과 정확한 position_ids key에만 둔다. 다른 key·prefix·모델·revision 전체에 일반 ignore 목록을 적용하지 않는다.
- 원본 파일 SHA/recipe/profile 검증은 그대로 유지한다. 원본 가중치를 삭제·변환하거나 classifier 검사를 약화하지 않는다.
- 저장된 위치 buffer의 dtype I64, shape[1,514], config.max_position_embeddings=514, 값 arange(514) 일치를 확인한다. loaded model의 같은 이름이 학습 parameter가 아닌 buffer인지, 재생성된 dtype/shape/value가 같은지도 확인한다. 차이가 있으면 실패한다.
- 이 검증을 통과한 buffer 하나만 persistent state 비교에서 별도로 처리한다. 나머지 저장/loaded key·shape는 정확히 같아야 한다. classifier 및 num_labels1·기존 raw-logit/token 정책도 유지한다. 예외 buffer가 없는 기존 정상 경로는 그대로 작동한다.
- 오류 보고에는 bounded missing/unexpected/mismatched key 목록·검증 단계만 기록한다. tensor 값 전체나 입력 문서/비밀은 출력하지 않는다. 추가 차이가 있으면 model_weights_mismatch를 유지한다.
- 독립 tiny 시험: 동일 legacy buffer 성공, buffer 없음 성공, 잘못된 dtype/shape/value 실패, 알 수 없는 extra key 실패, classifier 누락/shape 불일치 실패, 다른 model/revision에 예외 미적용. 실제 고정 SDK의 비영속 buffer 특성을 검증하고 기존134개·설치 회귀를 보존한다.

## 후속 실행 — 독립 검증 통과 후 한정

실제 진단만을 위한 무제한 model reload는 하지 않는다. 수정 검증 이후 첫 mMiniLM smoke 재실행 자체에서 정확한 normalized key 비교와 buffer 검증을 수행한다. 다시 실패하면 후속 모델을 멈추고 새 원인을 기록한다.

기존 실패20pairs/1worker를 포함하여 reranker smoke 상한을5workers/100pairs로 개정한다. 다른 embedding/full reranker 한도는 유지하므로 총 inference73workers/500pairs다. 이는 기존 실패를 지워 원래4회 안으로 넣는 방식이 아니다. 기존 E5/mMiniLM 재다운로드0, 남은 BGE 두 모델의 최초 준비는 각1회다. 이미 완료된 준비의 변환 추가0이며 기존 BGE-M3의 최초 tensor-only 변환은 유지한다. 단일 worker300초·RSS4GiB·normal pressure·최초 시작1795801676.159772부터2시간 deadline1795808876.159772는 유지한다. 원래 deadline이 지나면 이 계약으로 추가 실제 작업을 시작하지 않는다.

parent ledger/manifest/실패/검색 결과는 변경하지 않는다. 후속 execution ID와 새 설치/runner hash·정확 채택 SHA를 기록하고, 기존 시작 시각·다운로드·시도/예약 수를 계승한 별도 ledger를 연결한다. 이미 성공한 E5 실행은 재호출하지 않고 identity를 대조해 재사용한다. 새 실행은 같은 입력·정답·후보·모델 revision을 사용하며 qrels를 재채점하지 않는다.

계승 시 기존 counters는 embedding_smoke3, embedding_full21, reranker_smoke1, reranker_full0이며 다운로드 시도는 E5/mMiniLM 두 개다. 실패 pair의 실제 완료 수 null은 그대로 둔다. 추가 실제 추론은 최대48worker: BGE embedding smoke3/full21, mMiniLM·BGE reranker smoke4/full20이다. 같은 실패 호출을 자동 재시도하지 않고 이번 새 계약의 mMiniLM smoke 두 질문을 별도 label로 실행한다. 한 번 더 실패하면 추가 모델을 멈추고 원인을 남긴다.

첫 실제 smoke의 결과에 저장/loaded persistent state 비교, 정확 예외 buffer identity 검증과 나머지 차이 목록을 포함한다. stored/loaded key 목록이 예상과 다르면 실패하며 새로운 허용 목록을 즉석에서 추가하지 않는다. SDK/모델 revision/가중치 교체, 4GiB·시간 한도 증가, LLM/API·P013 호출은 허용하지 않는다.

기존 parent artifact hash, 최초 시작/deadline/실패/counter의 불변성 및 새 ledger의 총량 계승을 독립 테스트로 검증한다. 모델을 실제 호출하지 않는 테스트에서 budget 초과·deadline·불확실한 이전 worker·파일 변조가 실행 전에 거부되는지 확인한다. 새 설치물로 metadata/작은 buffer fixture와 기존 tiny SDK·패키지134개·하네스·1513 파일 보존을 대조하고, 실제 실행 결과와 비교 보고/UI를 정상 personal/dev에 전달한다.

이 후속 계약은 전체 P032 또는 최종 goal 완료가 아니다. S2/S3·생성/API/Drive·평가기·P013 grant·P029 C4 경계는 그대로다. 정확 후속 READY와 dev 채택 전에는 현재 run의 실제 호출 중지를 유지한다.
