# P006 준비 검토

검토일: 2026-10-23 Asia/Seoul
상태: 준비 완료

사용자가 PDF 등의 원문 추출·청킹과 여러 청킹 방식의 검색/최종 답변 평가를 기존 학습 흐름에 추가하도록 요청했다. 범위가 큰 만큼 P006 원문/기준선, P007 청킹/검색 비교, P008 답변/UI 비교로 순차 분리한다. P007/P008은 P006의 실제 산출물과 평가 계약을 검토한 뒤 준비 완료로 전환한다.

## 확인한 근거

- plan queue에서 P001~P005 모두 DONE이며 dev HEAD/personal-dev는 8d150f44251919f9326cb22778d0b8bcae72dae7이다. dev 작업 트리는 깨끗했다.
- docs/verification/p005/README.md: stage76/root19/단독 복사76 테스트 및 실제 모델·브라우저 증거, 고정 질문 생성 품질의 한계를 확인했다. 전체 품질이 충분하다고 가정하지 않는다.
- docs/feedback/dev/P005-runtime-metadata.md: 재시작 metadata 순서 비교 수정이며 모델/계약 변경이 아님을 확인했다.
- 제품 data/synthetic/README.md와 chunks.jsonl: 현재 원문 입력 없이 작성한 15개 가상 청크. 기존 원문을 추출한 것으로 설명할 수 없다.
- scripts/rag.py는 고정 chunks 경로를 기본으로 쓰고 build_dense_index.py는 --chunks를 받는다. 새 corpus 선택은 기존 코어의 인자 확장으로 연결 가능하며 별도 RAG 구현이 필요하지 않다.
- https://pypdf.readthedocs.io/en/stable/user/extract-text.html : 텍스트 추출 API·이미지 페이지 OCR 한계·PDF 처리 자원 한계.
- https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents : 크기/겹침·문서 구조·의미 단위 접근을 구분.
- https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-solution-design-and-evaluation-guide : 수집/청킹/색인과 질의/생성, 계층별 평가를 구분.

## 준비 판단

입력은 새 가상 원문만 사용하며 비공개 PDF 수집/공유나 계정 접근이 필요하지 않다. Python 격리 환경·pypdf와 fixture 도구 설치는 기존 E2E 구현 위임 범위다. 모델과 기존 데이터는 보존한다. 400/80 문자 설정은 검증 전 시작점으로 명시했다.

재현 가능한 canonical text·page map·half-open offset·chunk schema와 생성 규칙, 빈 페이지/이미지/추출 실패, 새 corpus 연결·실제 E2E·회귀·증거 기준이 구체적이다. 정답은 원문 fact/span에 고정해 후속 청킹 간 공정한 평가 기반을 마련한다. P006은 일반 PDF/OCR/표 인식의 완성이나 청킹 최적화 완료를 주장하지 않는다. 남은 P007 지표 산식·후보 그리드·P008 UI/평가 계약은 초안으로 명시해 자동 착수하지 않는다.
