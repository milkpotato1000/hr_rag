# 공개 모델로 배우는 RAG

먼저 준비된 가상 HR 문서와 저장 결과로 RAG의 각 단계를 이해하고, 같은 질문에서 한 가지 조건을 바꾸어 비교합니다. 구현과 검증은 Codex 또는 Claude Code에 맡기고, 학습자는 **왜 이 근거를 찾았는지, 답변에서 무엇이 빠졌는지**를 해석합니다.

이 안내는 P024의 첫 문서 증분입니다. 기본 방향은 Hugging Face(HF)의 공개 모델을 로컬에서 사용하는 것이며, 유료 LLM API는 후속 선택 기능입니다. **아래 두 JSON은 실행할 수 없는 설계 예시입니다. 현재 CLI에 전달하지 마세요.** 독립 API adapter와 validate/preview/invoke CLI는 P025에서 오프라인 검증까지 구현했습니다. [provider 안내](providers.md)를 참고하세요. [일반 문서 RAG CLI](document-rag.md)는 P026에서 연결해 오프라인 검증했습니다. [Drive 단일 문서 연결](drive.md)은 P027에서 구현하고 가짜 인증/HTTP로 검증했습니다. 실제 계정 연결은 미검증이며 [wheel 설치·독립 실습](install.md)은 P028에서 새 venv로 검증했습니다. [일반 문서 학습 UI](ui.md)는 실제 코어에 연결했고 합성 backend로 화면을 검증했습니다. 파일 선택창의 도구 정책 차단으로 브라우저 업로드 검증은 남아 있습니다. 기존 HR 평가 runner 통합은 후속입니다. P013 모델 실험은 사용자 요청으로 보류 중이며 이 안내가 재개 권한을 부여하지 않습니다.

[Hybrid 검색](hybrid.md)과 [고정 후보 리랭킹](reranking.md)은 설치 패키지·CLI/UI에 연결했습니다. 수기 fixture/tiny SDK/합성 화면을 검증했습니다. 이후 [E5 실제 검색 사례](live-retrieval-s1.md)를 추가했습니다. mMiniLM은 로더 검사에서 중단했고 BGE와 실제 리랭커 품질은 미검증입니다.

[단계별 비교 실습](experiments.md) → [모델과 지원 상태](models-and-support.md) → [로컬 예시](examples/local.json) / [API 예시](examples/api.json) 순서로 읽으세요. 전체 후속 순서는 [채택한 패키지 로드맵](../../planning/rag-package-roadmap.md)에 있습니다.

## 같은 흐름에서 LLM만 선택하기

아래는 두 모드가 공유할 목표 흐름입니다. 실제 연결이 완료된 범위는 지원 상태표에서 확인합니다.

```text
문서 선택·버전 저장 → PDF 읽기 → 청킹 → 공개 임베딩·검색
                                         ↓
질문 ───────────────────────────────→ 검색 후보
                                         ↓
                          리랭커 생략 / 공개 리랭커
                                         ↓
                            실제 전달 문맥 선택·기록
                                         ↓
                  답변 LLM: 로컬 공개 모델 / 선택 API(후속)
                                         ↓
                                답변 + 원문 인용
                                         ↓
                평가 LLM: 로컬 공개 모델 / 선택 API(후속)
                                         ↓
                     Python 집계 → 같은 질문으로 비교
```

| 선택 | 기본 공개 모델 경로 | 선택 유료 LLM API 경로 |
| --- | --- | --- |
| 답변 생성 | 기존 Ollama 기반 구현을 기준선으로 활용 | 독립 adapter 구현·오프라인 검증, 새 문서 CLI 연결·오프라인 검증 |
| 주장 추출·의미 판정 | 별도 평가 LLM 역할, P013 전체 검증 미완료·보류 | 독립 adapter의 역할 선택 구현, 평가 runner 연결은 후속 |
| 임베딩 | 공개 임베딩 사용 | 공개 임베딩 유지 |
| 리랭커 | none / 두 공개 CrossEncoder 비교·오프라인 검증 | 동일한 공개 모델 후보 유지 |
| 청킹 | 규칙 방식 또는 모델 기반 방식 | 규칙은 동일, schema v2 chunking 역할에서 LLM provider 선택 가능 |
| 비용·환경 | 기기 메모리·시간·전력 관찰 | LLM 호출 비용·지연과 로컬 검색 자원 관찰 |

생성 모델과 평가 모델은 다른 역할입니다. 향후 같은 모델 또는 서로 다른 모델을 지정할 수 있게 설계합니다. BM25, RRF, 고정 크기·재귀·제목/섹션 청킹은 알고리즘입니다. 의미 기반 청킹은 임베딩 유사도로 경계를 정할 수 있고, LLM 청킹은 별도 방식입니다. HF 모델은 임베딩·LLM·리랭커 등의 역할에서 선택합니다.

두 JSON의 최상위 항목과 LLM을 제외한 설정은 같습니다. `llm.generation`은 답변 생성, `llm.evaluation`은 추출·판정·정답 매칭의 설계상 설정입니다. `PLACEHOLDER_*`는 미결 값이며 지원 모델 이름이 아닙니다. `schema_status`도 후속 adapter에서 실제 스키마를 정한다는 뜻입니다. `evaluation`은 측정 정책이고 `llm.evaluation`은 그때 사용할 모델 역할입니다.

## 지금 읽을 수 있는 원문과 결과

- [장문 가상 HR 규정집 PDF](<../../../2. Document Chunking/data/source-v4/output/pdf/hr-handbook.pdf>)와 [PDF에서 추출한 연속 텍스트](<../../../2. Document Chunking/data/source-v4/extracted/canonical/hr-v4-handbook.txt>): 같은 문서를 다른 단계에서 보는 자료입니다. 페이지와 청크는 같은 단위가 아닙니다.
- [청킹 학습 안내](<../../../2. Document Chunking/LEARNING.md>): 고정·재귀·구조·의미·LLM 방식의 저장 결과를 비교합니다. 이 단계 화면의 문맥 선택은 시뮬레이션이며 답변 생성까지 통합된 화면은 아닙니다.
- [Naive RAG 학습 안내](<../../../1. Naive RAG/LEARNING_GUIDE.md>)와 [LangChain 구현](<../../../1. Naive RAG/variants/langchain/README.md>): 기존 합성 청크 기준선입니다. 장문 source-v4와 자동으로 같은 corpus가 되지 않습니다.
- [P013 중지 기록](../../verification/p013/recovery-20261127/README.md): 기존 8B 한 요청의 성공과 메모리 중지는 전체 평가 완료를 뜻하지 않습니다.

샘플은 가상 자료입니다. 이후 개인 문서를 연결하면 문서 권한·버전과 정답을 새로 관리해야 합니다. 기존 청킹 단계의 Drive fixture는 로컬 샘플 복사입니다. 별도 P027 connector는 실제 REST/OAuth 코드를 제공하지만 개발 시험은 가짜 인증/HTTP만 사용했고 Google Drive 계정에 접속하지 않았습니다.

## 호출 없이 시작하기

다음은 `hr_rag_dev/`에서 실행하는 읽기·오프라인 확인입니다. 모델이나 서버를 시작하지 않습니다.

```sh
python3 -m json.tool docs/learning/rag-package/examples/local.json
python3 -m json.tool docs/learning/rag-package/examples/api.json
python3 scripts/contract_guard.py check
python3 scripts/work_queue.py --owner dev
python3 '1. Naive RAG/scripts/run_bm25_baseline.py' --help
```

BM25 기준선은 표준 라이브러리만으로 실행할 수 있습니다. 아래 결과 경로가 이미 존재하면 새 이름을 사용하세요. source-v4의 실험과는 별도인 기존 합성 샘플입니다.

```sh
python3 '1. Naive RAG/scripts/run_bm25_baseline.py' \
  --chunks '1. Naive RAG/data/synthetic/chunks.jsonl' \
  --queries '1. Naive RAG/data/synthetic/queries.jsonl' \
  --top-k 20 --k 5 10 20 \
  --output-dir /tmp/hr-rag-bm25-learning-01
```

## 코딩 도구에 맡기는 방법

두 도구 모두 이 저장소의 AGENTS.md와 역할 규칙을 따릅니다. 새 요구는 plan에서 범위·검증을 확정하고, dev가 정확한 커밋을 채택한 뒤 구현합니다. 도구 구독을 RAG의 LLM API 이용권으로 취급하지 않습니다.

Codex에 복사할 요청:

> hr_rag_dev의 AGENTS.md와 현재 채택 계약을 읽어줘. P024 학습 문서와 기존 저장 결과만 사용해서 생일휴가 질문의 검색 후보→실제 전달 근거→답변 누락을 설명해줘. 내가 예상할 항목과 확인할 지표를 먼저 제시해줘. 모델 실행·다운로드·서버 시작·API 호출·P013 재개는 하지 말고, 새 구현 요구가 생기면 plan 접수 절차를 따라줘.

Claude Code에 복사할 요청:

> 이 프로젝트의 AGENTS.md 및 해당하는 CLAUDE.md를 읽고 dev 역할을 유지해줘. docs/learning/rag-package의 두 example_only JSON을 비교해서 LLM 교체와 임베딩 교체의 차이를 설명해줘. 기존 파일과 오프라인 BM25 결과로만 검증하고 결과 경로를 기록해줘. 신규 adapter는 구현하지 말고 plan→정확 채택→dev 절차로 요구를 남겨줘. P013 보류를 유지하고 모델·서버·유료 API를 실행하지 마.

## API를 선택하기 전에 이해할 점

향후 API 모드는 선택한 역할에 따라 질문·문서 일부·답변·평가용 정답이 provider로 전송될 수 있습니다. 사용할 문서의 전송 권한과 provider의 데이터 처리 조건을 확인합니다. 키는 저장소·JSON·로그에 넣지 않고 환경 변수 또는 별도 비밀 저장소에 보관합니다. 예시에는 키 값 대신 `api_key_env` 이름만 있습니다.

API 실패 시 조용히 로컬로, 로컬 실패 시 API로 바꾸지 않는 것이 설계 원칙입니다. 선택한 provider와 오류를 기록하고 비교를 중단해야 비용과 재현 조건을 알 수 있습니다. 독립 adapter의 실패 처리는 오프라인 검증했으며 실제 API 연결은 미검증입니다. 일반 문서 연결은 [P026 안내](document-rag.md)를 따릅니다. 측정하지 않은 토큰·비용·메모리는 `미측정`으로 표시하며 0으로 간주하지 않습니다.

[BM25/Dense/Hybrid 비교](hybrid.md)는 별도 검색 실행 허용과 공개 HF 설정을 사용합니다. 실제 SDK tiny 모델·합성 검색 검증과 [한 규정집의 E5 검색 실험](live-retrieval-s1.md)을 완료했습니다. 일반적인 한국어 품질을 보장하는 결과는 아닙니다.


다섯 방식의 저장 경계 생성·재생·파생·원문 fact 비교는 [모델 청킹 실습](model-chunking.md)을 참고하세요. 의미/LLM 청킹은 등록 설정과 별도 실행 권한으로 연결되며 실제 한국어 모델 품질은 미검증입니다.

현재 설치는 [최신 dev 설치](install-current.md)와 [모델 준비](model-preparation.md)에서 시작합니다. 공개 embedding/reranker의 고정 파일 준비·자동 manifest와 local/API/mixed LLM spec을 사용합니다. 준비·추론·품질 상태는 구분합니다.
