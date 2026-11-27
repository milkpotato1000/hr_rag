# P032 S1 mMiniLM 위치 buffer 호환성 검토안

2026-11-28 DRAFT. 현재 중단된 live run을 재개하지 않는다. 코드·독립 시험과 정확 후속 READY를 검토한 후에만 추가 실제 호출을 허용한다. P013 평가기/메모리 recovery와 무관하다.

## 실제 중단과 읽기 증거

run001은 E5 준비와 smoke3 worker, 본 검색21 worker를 완료했다. BM25/E5 Dense/E5 Hybrid 각10질문 결과가 저장됐고 생성0이다. mMiniLM의 공개 파일 준비는 성공했지만 첫20pair smoke worker가 model_weights_mismatch를 반환하여 ledger가 halted가 됐다. 해당 시도는 reranker_smoke1, 요청20pairs로 남고 성공/완료 pair로 바꾸지 않는다. worker는 종료됐고 sampling peak928579584bytes, OS pressure normal이었다. BGE 두 모델 준비·추론은 아직 하지 않았다.

plan은 원본 가중치를 모델로 로드하지 않고 safetensors header와 작은 buffer bytes, 설치 SDK 소스만 읽었다. 실제 mMiniLM revision1427fd652930e4ba29e8149678df786c240d8825의 파일에는202 tensors가 있고 non-weight/bias 항목은 `roberta.embeddings.position_ids` 하나다. dtype I64, shape[1,514], 값514개는 config.max_position_embeddings=514의 arange와 정확히 일치한다. config.model_type은 xlm-roberta다. 정렬 JSON header의 SHA256은7dff17d06a7a5f20b49cc764959acdd9fa9f647c6cc787358f95816eadc313a8이다.

설치된 transformers5.24.1의 `models/xlm_roberta/modeling_xlm_roberta.py`68행은 같은 position_ids를 `nn.Buffer(torch.arange(config.max_position_embeddings).expand((1, -1)), persistent=False)`로 만든다. 기존 reranker_worker는 저장 tensor key/shape 전체와 loaded model.state_dict 전체의 완전 동일성을 요구한다. 따라서 이 비영속 buffer가 불일치의 유력한 원인이다. 아직 실제 loaded/stored 전체 diff를 수집하지 않았으므로 다른 불일치가 전혀 없다고 단정하지 않는다.

## 수정 후보의 엄격한 범위

- 지원 예외는 위 고정 mMiniLM 모델 ID/revision과 정확한 position_ids key에만 둔다. 다른 key·prefix·모델·revision 전체에 일반 ignore 목록을 적용하지 않는다.
- 원본 파일 SHA/recipe/profile 검증은 그대로 유지한다. 원본 가중치를 삭제·변환하거나 classifier 검사를 약화하지 않는다.
- 저장된 위치 buffer의 dtype I64, shape[1,config.max_position_embeddings], 값 arange 일치를 확인한다. loaded model의 같은 이름이 학습 parameter가 아닌 buffer인지, 재생성된 dtype/shape/value가 같은지도 확인한다. 차이가 있으면 실패한다.
- 이 검증을 통과한 buffer 하나만 persistent state 비교에서 별도로 처리한다. 나머지 저장/loaded key·shape는 정확히 같아야 한다. classifier 및 num_labels1·기존 raw-logit/token 정책도 유지한다. 예외 buffer가 없는 기존 정상 경로는 그대로 작동한다.
- 오류 보고에는 bounded missing/unexpected/mismatched key 목록·검증 단계만 기록한다. tensor 값 전체나 입력 문서/비밀은 출력하지 않는다. 추가 차이가 있으면 model_weights_mismatch를 유지한다.
- 독립 tiny 시험: 동일 legacy buffer 성공, buffer 없음 성공, 잘못된 dtype/shape/value 실패, 알 수 없는 extra key 실패, classifier 누락/shape 불일치 실패, 다른 model/revision에 예외 미적용. 실제 고정 SDK의 비영속 buffer 특성을 검증하고 기존134개·설치 회귀를 보존한다.

## 후속 실행 후보 — 아직 승인/재개 아님

실제 진단만을 위한 무제한 model reload는 하지 않는다. 수정 검증 이후 첫 mMiniLM smoke 재실행 자체에서 정확한 normalized key 비교와 buffer 검증을 수행한다. 다시 실패하면 후속 모델을 멈추고 새 원인을 기록한다.

후속 READY에서 기존 실패20pairs/1worker를 포함하여 reranker smoke 상한을5workers/100pairs로 명시 개정하는 안을 검토한다. 다른 embedding/full reranker 한도는 유지하므로 총 inference73workers/500pairs다. 이는 기존 실패를 지워 원래4회 안으로 넣는 방식이 아니다. 파일 재다운로드0, 변환 추가0, 단일 worker300초·RSS4GiB·normal pressure·최초 시작1795801676.159772부터2시간 deadline1795808876.159772는 유지한다. 원래 deadline이 지나면 이 안으로 재개하지 않는다.

parent ledger/manifest/실패/검색 결과는 변경하지 않는다. 후속 execution ID와 새 설치/runner hash·정확 채택 SHA를 기록하고, 기존 시작 시각·다운로드·시도/예약 수를 계승한 별도 ledger를 연결한다. 이미 성공한 E5 실행은 재호출하지 않고 identity를 대조해 재사용한다. 새 실행은 같은 입력·정답·후보·모델 revision을 사용하며 qrels를 재채점하지 않는다.

이 안은 전체 P032 또는 최종 goal 완료가 아니다. S2/S3·생성/API/Drive·평가기·P013 grant·P029 C4 경계는 그대로다. 정확 후속 READY와 dev 채택 전에는 현재 run의 실제 호출 중지를 유지한다.
