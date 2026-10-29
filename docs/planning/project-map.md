# Project A · B · C 학습 프로젝트 정의

2026-10-29 사용자가 이 채팅에 제공한 ChatGPT 기획 정의를 기준으로 한다. 프로젝트 구분·학습 목표를 확정하며 A/C의 로컬 저장소 위치나 구현 완료를 추정하지 않는다.

| 프로젝트 | 주제 | 핵심 학습 목표 |
| --- | --- | --- |
| Project A | NL2SQL + Tool Calling Agent | Semantic Layer, Structured Outputs, Tool Calling, SQL 정확도·평가 |
| Project B | RAG → Agentic RAG | 문서 추출·청킹·검색·Reranking·RAG 평가·ReAct·Human-in-the-Loop·운영/서빙 |
| Project C | Multi-Agent Orchestration | 전문 Agent 구성, 질문 분해·분배, Orchestrator, Agent 간 협업 |

A는 자연어 질문→의도/도구 선택→SQL 실행→결과 검증→답변을 학습한다. B는 가상 HR 규정 PDF로 Naive RAG를 구축하고 Advanced/Agentic RAG로 확장한다. A와 B를 별도로 개발한 뒤 C에서 HR·데이터 분석·계산 등 전문 Agent를 조율하는 구조를 학습한다. 현재 `hr_rag` 전체가 **Project B**다. A/C의 폴더나 진행 상태는 이 저장소만으로 확인하지 않는다.

## Project B의 학습 영역

1. Naive RAG: 원문/청킹→임베딩→Dense 검색→근거 기반 답변.
2. Advanced RAG: BM25+Dense→Hybrid(RRF)→Cross-Encoder Reranking. Recall@K/MRR/nDCG 등으로 검색 성능 평가.
3. RAG Evaluation: Claim Extraction→Faithfulness/Answer Correctness, LLM/NLI 평가기 비교. 답변 생성과 논리적으로 분리한 **B 내부 평가 모듈**이다.
4. Agentic RAG: 추론 설정·ReAct·Tool Calling·재검색·근거 검증·사람 검토/Slack 에스컬레이션. 내부 추론 전문의 수집/표시를 완료 조건으로 삼지 않고 도구 선택·실행 결과·근거·종료 상태로 동작을 검증한다.
5. 운영/서빙: Google Drive 개정/삭제/권한 동기화, Ollama/vLLM 동일 조건 비교.

위 목록은 영역 구분이며 세부 실행 순서는 최신 사용자 요청에 따라 **P015 원문 PDF 재작성 → P007 청킹·검색 실험 → P013 기본 평가기 → P014 NLI 비교 → P008 답변 비교 UI → P010 Hybrid**다. P012는 완료됐고 하네스는 별도 프로젝트로 분리했다. Cross-Encoder Reranking·Agentic/Human-in-the-Loop·실제 Drive·서빙 비교는 후속 상세 계약으로 준비한다. A/B/C는 프로젝트 구분, P번호는 작업 식별자, 번호 폴더는 B 안의 큰 구현 단계다.

## 현재 확인된 구현 상태

dev 완료 커밋 `64cd00c`와 작업 큐 기준으로 Naive E2E, BM25/Dense, 원문 추출·고정 청킹 기준선, ID 인용, LangChain 채택·기본 학습/별도 비교 UI(P001~P006/P009/P011/P012)가 완료됐다. 다양한 청킹 실험은 이 기준선과 구분한다.

P015 원문 재작성은 준비 완료이며 dev의 정확한 채택 후 착수한다. Hybrid(P010), 자동 LLM 평가기(P013), NLI 평가기 비교(P014), 다양한 청킹(P007)/평가 화면(P008)은 초안이다. Cross-Encoder Reranker·Agentic·실제 Drive/Slack·vLLM은 후속 계획이다. 사용자 설명의 “모두 B에 속함”은 분류를 뜻하며 이 항목들이 이미 모두 구현 완료됐다는 뜻으로 기록하지 않는다.

이전 답변 및 초기 등록 문서에서 “B=평가 모듈 전체, A/C 미확인”으로 좁혀 해석한 부분은 이 정의로 정정한다. 평가 모듈 분리·P013/P014의 역할은 유지하고 실행 순서는 위의 최신 요청을 따른다. 현재 로드맵은 [RAG 학습 로드맵](naive-rag-roadmap.md), 평가 상세는 [B 내부 Generation Evaluation](../architecture/project-b-generation-evaluation.md)을 따른다.
