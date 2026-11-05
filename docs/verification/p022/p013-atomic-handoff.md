# P013 연결용 원자 정답 후보 인계

새 후보는 preparation/artifacts/run003/packet.json이다. 실제 정답 승인은 null이며
P013은 DRAFT다. 실행 준비·정답 승인·평가 실행을 이 인계로 대체하지 않는다.

- schema_version2 / review_version p022-atomic-v1
- 패킷 SHA: `946d7181ecf8b45e633a347adbcc241f38dfd5976d80342e34e1da3bf2d87199`
- 질문10개, 후보57개(질문별10,3,9,6,4,7,8,10,0,0), 판정18개
- 이전45개는 모두 revision-mapping.json에서 한 번씩 연결된다. 독립 사실 분리10개, 적용 조건 복원2개, 유지33개다.
- atomicity-audit.json은 exact plan의 동결 제안이며 파일 SHA e9dd80869464b6e41d3e7f77482a2908702b9eb742a410c78a8c7bff337140ae다.
- source-v4 canonical SHA 1c6867d284d136b2eb1cf6f9a707506480946988eaa155ae46b13ce25e2eb298과 부모 run002 패킷 e6a264387d3dd169168bcf1733156bf91bd4bdf76fc8bb70f5a704e3bc7a2b0e를 보존한다.
- quote/span/page/hash/답변 위치는 재검산했다. 정확한 파일 hash는 run003/packet-manifest.json과 atomic-delivery.json에 있다.

P013의 고정 답변 추출 기대값도 자격/수량·기한/경로/승인 주체·기록 대상을 독립 사실로
검토하되 대상자/조건/부정·연간/주간 단위를 보존한다. 조건부 작업·구분 관계는 단어로
쪼개지 않는다. 동일 조건 반복이나 공유 인용을 추가 가산 사실로 계산하지 않는다.
이번 작업에서는 P013 기대값/과거 run/평가 점수를 실제 변경하거나 추출 모델을 실행하지 않았다.
45개 버전과57개 버전은 분모가 달라 동일 평가 버전의 품질 향상으로 직접 비교할 수 없다.

새 run003 UI의 실제 화면·좁은 폭·키보드 검증은 아직 남아 있다. run002에 대한 사용자
관찰이 새 run003에 자동 전이되지 않는다. 이 항목이 확인되기 전 P022 전체 완료는 아니다.
