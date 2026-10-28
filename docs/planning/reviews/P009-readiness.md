# P009 준비 검토

검토일: 2026-10-28 Asia/Seoul
상태: 준비 완료

## 요청과 검토 근거

사용자가 인계된 ID-only 인용 방식을 현재 Naive 프로젝트에 계획하고 반영하도록 직접 지시했다. 이전 전달만 요청 상태를 넘어 이 변경의 기획·구현을 승인한 범위다. 기존 dev 인계 위임에 따라 이 과제를 등록한다.

검토한 dev HEAD는 6644bac5d6a0e2511bf7df61002a79590e935bdd, 채택 plan은 d52bf59d7e208e255c0a1774845446e955b38193이다. 작업 트리는 깨끗했고 contract_guard PASS를 확인했다. 큐에는 P001~P006 완료와 P007/P008 초안이 있다. 다음 미사용 번호 P009, 우선순위65/선행P006으로 현재 개선을 별도 등록한다.

실제 scripts/rag.py validate_answer는 모델 quote의 exact substring을 검사한다. generation.py SCHEMA와 generation-lock.json, setup_generation.py는 같은 정적 응답 계약을 공유한다. prompts/system-v2.txt는 이미 정확 복사·부정 답변의 answered·temperature0 구조를 사용한다. 단순 지시문 강화가 아니라 모델/코드 책임 변경이 필요하다. serve.py의 system-v2 상태 표시와 fake provider 테스트까지 함께 변경해야 혼용을 방지할 수 있다.

docs/feedback/dev/P006-pdf-citation-and-interfaces.md와 docs/verification/p006/live/q06.json/README.md에 PDF 줄바꿈 복사 실패가 기록돼 있다. 식대 질문의 “휴:” 삽입 사례는 전달받은 보고이며 P009에서 실제 같은 질문을 재검증한다. 최초 현상이 매번 동일하게 재현된다고 가정하지 않는다.

## 계약 판단

- 기존 chunk_id와 문맥 snapshot을 재사용하고 인용 단위를 전체 chunk text로 고정해 새로운 ID/문장 매핑 체계가 불필요하다.
- dynamic schema enum과 독립 코드 검증을 함께 요구하며 요청 간 공유 mutable 상태를 금지한다. 추가 키/중복/잘못된 ID는 보정하지 않는다.
- 최종 API citations는 기존 메타데이터+quote 형태를 유지하므로 화면 호환성과 원문 완전 일치를 함께 검증할 수 있다.
- P004 역사적 계약/증거는 보존하고 P009가 현재 실행 계약의 quote 생성 부분만 대체한다. 새 버전 lock/prompt로 차이를 명시하며 모델·검색·source-v2는 보존한다.
- 실제 모델·UI·14질문 및 PDF 관찰을 요구하되 인용 구조 개선을 답변 의미 품질 보장으로 과장하지 않는다. 식대 정상 응답은 실제 완료 기준이다.
- 유료 API/외부 Drive/새 모델/배포 없이 기존 로컬 환경에서 수행 가능하다. 추가 업무 결정은 없다.

범위·선행·실패/회귀·실제 검증·완료 기준이 준비돼 P009를 준비 완료로 등록한다. P007/P008은 이번에 실행하지 않는다.
