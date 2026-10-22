# P004 기획 준비 검토

검토일: 2026-10-22 Asia/Seoul
상태: 준비 완료

## P003 완료와 준비 근거

사용자는 Naive RAG E2E를 Codex가 구현·검증하고 본인은 의미·평가·최적화 실험으로 학습하기를 요청했다. P문서별 순차 진행 지시에 따라 P003이 끝난 후 이번 생성 계약을 준비 완료로 등록한다.

dev와 personal/dev는 `74b3c35a551671e1387904a0715ea5f8a1625a0c`로 일치하고 작업 트리는 깨끗하다. P003 큐는 DONE 6/6이다. 다음 커밋된 증거를 읽어 검토했다.

- docs/verification/p003/README.md와 06-final-tests.txt: 기존37개 포함 총53개 PASS, 첫 readiness timeout·cosine 비교 실패와 수정 이력 보존.
- 07-live-final/commands.txt, delivery-checks.json: 실제 BGE-M3 F16/1024차원·모델 digest, 서비스 start/status/stop, 영속색인·새 프로세스 재open, 단독복사와 원본 보존.
- 07-live-final/index-manifest.json·payload-mapping.json: 15청크와 원문 payload·UUID·hash·1024차원·Cosine의 연결.
- 07-live-final의 두 검색 결과와 08-comparison.json: 같은14질문·K에서 Dense Recall@5=1, BM25=0.893939. 근거 없는3질문 모두 Dense 결과가 있어 검색 결과 존재와 근거 충분성을 분리해야 한다.
- 09-contract-and-queue.txt: 채택plan·완료조건·최신PASS·비어있지 않은 증거·index guard·큐·Git제외 일치. 기존P001/P002 계약·증거 보존.

이 경로들은 dev에 커밋된 증거이며 구현 이력을 plan으로 병합하지 않는다.

## 이번 계약의 판단

실제 모델·격리환경·색인·질문·검색결과가 준비돼 생성 단계를 독립적으로 검증할 수 있다. Qwen3:4b Q4_K_M을 같은 Ollama에 추가하며 공식 배포의 크기·라이선스와 chat API를 확인했다. 실제digest·양자화·template는 별도 generation-lock.json에 기록해 기존 임베딩lock과 색인 정합성을 유지한다.

단일검색·단일생성만 연결한다. 전체청크 문맥예산·정답분리·유효원문인용·모델보류와 실행장애의 구분을 고정했다. 유효한 인용ID만으로 의미정확성을 승인하지 않도록, 실행 전 원문rubric과 실제14질문 검토를 요구한다. 검토자가 Codex인지 사람인지 정확히 표시한다.

P003의 search/runtime 구현과 설정을 재사용한다. Qdrant 영속색인은 생성모델 추가로 불필요하게 다시 만들지 않는다. 사용자에게 설치·테스트 구현을 넘기지 않고 이번 카드 안에서 실제 다운로드·로컬 생성·검증을 수행한다.

완료돼도 화면·학습가이드까지 E2E 인계가 끝났다고 부르지 않는다. P004 결과를 검토하고 P005 계약을 준비한다. 후속큰단계·유료API·외부계정·배포는 포함하지 않는다.
