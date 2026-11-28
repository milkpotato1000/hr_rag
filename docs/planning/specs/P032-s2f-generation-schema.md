# P032 S2f · 로컬 규정집 답변의 구조 지정

## 준비 검토

S2e의 동일 gt01 입력에서 4B가 입력 1,778토큰·출력 1,987토큰으로 stop을 반환했다. provider JSON 파싱을 통과하고 business_answer의 invalid_answer_schema에서 종료했다. 어느 필드가 잘못됐는지는 관찰할 수 없다. S2e 결과·ledger·원문·프롬프트를 보존한다. dev가 S2e의 정리·커밋을 끝낸 후 본 계획을 정확 채택한다.

현재 ask와 answer-from-rerank는 모두 llm.preview/invoke 및 business_answer를 사용한다. Ollama의 format=json은 업무 필드의 구조를 지정하지 않는다. [Ollama 구조화 출력 문서](https://docs.ollama.com/capabilities/structured-outputs)에 따라 로컬 RAG 생성에서 같은 업무 계약을 JSON Schema로 전송한다. 실제 설치된 서버와 모델에서 동작하는지 확인하는 것이 이번 시험이다.

## 구현 및 검증

- Ollama 규정집 답변 경로에서 루트 object에 status, answer, citations를 required로 지정하고 additionalProperties=false를 적용한다. status는 answered 또는 abstained, answer는 문자열, citations는 chunk_id 문자열 하나를 가진 object의 배열이다. chunk_id enum은 그 질문에 실제 전달된 ID에서 구성한다. 빈 문맥은 기존 무호출 보류 처리한다. 일반 LLM 호출과 다른 역할·provider의 기존 계약을 유지한다.
- 두 진입점에서 동일한 schema를 preview와 실제 전송에 사용하고 요청 fingerprint에 반영한다. 기존 응답 파서가 공백 답변·인용 중복·후보 밖 ID·상태에 맞지 않는 인용 수를 독립적으로 검사한다. 실패 시 필드 위치와 종류를 허용 목록의 코드로 기록할 수 있다. 원시 모델 출력이나 thinking은 보관하지 않는다.
- 모델 없는 시험으로 두 경로의 실제 요청 body, preview 일치, 추론 내용 폐기, 올바른 답변 및 보류, 잘못된 필드/인용 거부와 과거 산출물 읽기를 확인한다. 새 wheel과 독립 설치를 검증하고 변경 범위 회귀를 수행한다.
- S2e와 동일한 모델 digest·think=true·temperature 0.6·출력 4096·문맥 8192·질문·전달 청크와 messages를 사용한다. 실제 요청 body 차이는 format에 한정하고 별도 run에 보존한다. 이전 서버 종료 및 현재 모델 identity/자원 확인 후 gt01을 한 번 실행한다. 실제 answered 결과의 필수6개와 각 인용의 원문 지지, 부정·기한·추가 주장을 직접 검토한다.
- gt01 기술·내용 통과 후에만 gt02를 한 번 실행한다. 최대5일·다음 해 3월31일·생일 특별휴가 제외의 세 항목을 검토한다. 두 질문이 모두 통과하면 같은 설치와 설정에서 gt03~10을 각각 한 번 실행한다. gt03/08의 문맥 누락과 생성 누락을 구분하고 gt09/10은 금액 발명과 적절한 보류를 확인한다. 단일 모델의 10문항 결과로 기록한다.
- 전용 ledger에 질문당 1회, 최대10회(이전 두 실행 포함 누적12회), 순차1, 자동 재시도0으로 기록한다. 전체 90분, 질문당 HTTP480초/watchdog510초, RSS8GiB·pressure·소유권·unload·불확정 시 중단은 S2e 기준을 적용한다. /ps 5초 간격 및 pre/post metadata 포함 총1200회 이내. 시간·자원 한도나 기술 실패 시 남은 문항을 미실행으로 표시한다. 실제 결과는 원문·문맥·최종답변·인용·필수항목별 검토를 한 화면에서 읽을 수 있게 학습 목차에 연결하고 정상 dev push한다. Drive·P013/P014 평가기·LLM 청킹은 보류한다.
