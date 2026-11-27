# 공개 모델 기반 RAG 교육·구축 패키지

2026-11-27 사용자 최종 목표와 후속 결정에 따른 확장 로드맵이다. 기존 HR Naive/청킹 단계는 재사용 가능한 기준선으로 보존한다. 기존 project-brief/naive-rag-roadmap의 역사적 진행 표시보다 이 문서의 새 패키지 범위와 최신 dev 증거를 우선한다. P번호별 세부 실행은 정확 채택한 계약을 따른다.

## 사용자가 완성할 흐름

문서 저장소 연결 → 모델 선택 → 청킹 선택 → 임베딩·검색 선택 → 리랭커 선택 또는 생략 → 근거를 포함한 답변 → 같은 질문으로 비교·평가 → 설정 저장·재실행.

Claude Code와 Codex 모두 같은 저장소, 명령, 설정, 샘플 문서와 학습 가이드를 사용한다. 특정 코딩 도구의 구독을 LLM API 이용권으로 취급하지 않는다. HR은 기본 예제이며 다른 도메인 문서도 같은 흐름으로 연결한다. 모든 웹하드 URL을 자동 지원한다고 약속하지 않고 지원 커넥터와 인증·파일 형식을 명시한다. 최초 실제 저장소 대상은 기존 사용자 선택인 Google Drive다.

## 두 모델 사용 경로

| 구성 | 기본: 공개 모델 | 선택: 유료 LLM API |
| --- | --- | --- |
| 답변 생성·주장 추출·의미 판정 | HF 공개 모델 계열, 로컬 Ollama 실행부터 | 사용자가 가진 API 키·지원 provider·모델로 해당 LLM 역할 교체 |
| 임베딩 | HF 공개 모델 | 동일한 공개 임베딩 유지 |
| 리랭커·NLI | HF 공개 모델 후보 | 동일한 공개 모델 유지, NLI는 선택 실험 |
| 청킹·검색·평가 산술 | 오픈소스 코드, 필요 시 선택한 LLM 사용 | 같은 코드와 데이터 계약 사용 |

모델 모드와 LLM 역할은 분리한다. 생성과 평가 모델을 같은 모델 또는 서로 다른 모델로 선택할 수 있다. LLM 기반 청킹도 같은 provider 경계를 사용한다. API는 선택 기능이며 키가 없어도 로컬 경로와 오프라인 학습 예제가 가능해야 한다. 기본 경로에 유료 judge, 외부 검증기, 유료 임베딩을 숨은 의존성으로 넣지 않는다. 이전 Jev/CDM 아이디어는 기본 필수 단계에서 제외하고 별도 요청 시 검토하는 선택 확장으로 남긴다.

BM25, RRF, 고정/재귀/구조 기반 청킹은 모델이 아닌 알고리즘이다. 이들을 HF 모델로 억지로 교체하지 않는다. HF의 인기도와 공식 배포·라이선스·한국어 평가·메모리·런타임 호환성을 함께 확인해 후보를 정한다. 다운로드 순위를 품질 보증으로 표현하지 않는다. 공개 가중치와 완전한 오픈소스의 의미 차이를 표시하고 사용·배포 조건을 기록한다.

## 초기 후보와 선택 기준

후보 목록이며 설치·실행 완료 또는 현재 고정 모델과 동일하다는 뜻은 아니다. 정확 revision, 양자화 파일/digest, tokenizer, runtime, 입력 정책은 실행 카드에서 고정한다. 자동 최신 모델 변경은 하지 않는다.

| 역할 | 초기 비교 후보 | 공식 근거와 주의점 |
| --- | --- | --- |
| 생성·LLM 평가 | Qwen/Qwen3-8B와 같은 Qwen 계열의 소형 후보 | [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B), Apache-2.0 표시. 기존 Ollama 태그와 HF 원본·변환본 관계를 확인해야 함 |
| 임베딩 | BAAI/bge-m3, intfloat/multilingual-e5-small | [BGE-M3](https://huggingface.co/BAAI/bge-m3), [E5-small](https://huggingface.co/intfloat/multilingual-e5-small): MIT 표시. E5 query/passage 접두어·길이 정책 등 모델별 전처리 필요 |
| 리랭커 | BAAI/bge-reranker-v2-m3 | [공식 카드](https://huggingface.co/BAAI/bge-reranker-v2-m3): Apache-2.0 표시, 질문·문서 쌍 점수화. 모델 간 raw score를 동일 척도로 가정하지 않음 |
| NLI | 기존 P014 다국어 NLI 후보 | 실제 한국어 검증 및 라이선스·입력 한도 확인 후 확정, 첫 설치 필수 아님 |

공식 카드 확인일: 2026-11-27. 인기도 수치의 기준 시점과 측정 종류는 모델 카탈로그를 확정할 때 기록한다. 현재 M1 16GB에서는 모델 순차 로딩을 기본 설계로 하며 파일 용량과 실행 메모리를 구분한다. 8B 실행 성공·여유 메모리는 아직 검증되지 않았다. 기존 4B Thinking 변형을 일반 Qwen3-4B와 같은 모델로 표기하지 않는다.

## 단계별 구성

| 순서 | 산출물 | 상태·연결 |
| --- | --- | --- |
| 0 | 두 경로 학습 안내, 공통 설정 예시, 지원/미지원 표, 비교 절차 | P024 완료. 문서·예시, 모델 실행 없음 |
| 1 | LLM provider 인터페이스와 로컬/API adapter, 설정 검증·기록 | [P025](plans/P025.md) 구현, [P026](plans/P026.md) 일반 문서→답변 통합 완료(offline 검증). offline transport 시험 → 명시적 live 실행 분리 |
| 2 | 평가 기준선 완성 | P013 기존 성공/실패 보존. 현재 로컬 실험 보류, 명시 재개 또는 별도 승인된 대체 실행 계약 필요. P014 NLI 비교로 이어짐 |
| 3 | 생성·평가와 청킹 비교 UI 통합 | P007/P017 완료 재사용, P008의 답변·평가 표시 연결 |
| 4 | Dense 임베딩 모델 교체, Sparse/BM25, Hybrid RRF 비교 | P010에 모델 선택·index fingerprint 계약 확장 준비. 기존 선행 순서 유지 |
| 5 | 리랭커 없음/있음 및 모델별 비교 | Hybrid 이후 P020. 동일 후보 집합에서 순위·지연 비교 |
| 6 | 실제 Google Drive 문서 연결·변경 반영 | [P027](plans/P027.md) READY. 단일 Drive 문서 연결 계약에 따라 구현; 자동 sync는 후속 |
| 7 | 공통 설정 기반 UI·CLI 통합과 설치 패키지 | [P028](plans/P028.md) 설치·독립 샘플 READY(P027 완료 후). [P029](plans/P029.md) Drive 링크·모델 form·원문/청크/답변 비교 UI READY(P028 완료 후). 깨끗한 환경과 실제 도구 검증 범위를 구분 |

완료 근거: dev의 P001~P007, P009, P011/P012, P015~P017, P019, P021~P023. P013은 전체 완료가 아니다. P014/P008/P010/P020은 후속 계약이며 로드맵 등록만으로 실행하지 않는다. 구현 순서는 의존성에 따르고 최종 사용자 화면의 단계 순서와 다를 수 있다. 모델 실험 중지와 무관한 adapter·문서·fixture 개발은 별도 READY 범위에서 진행 가능하다.

`1. Naive RAG/`, `2. Document Chunking/` 및 독립 evaluation 모듈을 보존한다. `3. Hybrid RAG/`는 기존 계획을 따른다. 모든 세부 P마다 새 번호 폴더를 만들지 않는다. 공통 패키지로 추출할 모듈·원본 commit/hash·호환 범위는 해당 구현 카드에서 정한다. Agentic 및 A/C 프로젝트는 이 패키지 기본 완성의 필수 선행이 아니다.

## 비교·평가 계약

- 한 번에 한 축을 바꾼다. 질문·원문 snapshot·정답 버전·seed/생성 설정·실행 환경을 기록한다. 청킹/임베딩 변경 시 index를 재생성하고 이전 index를 재사용하지 않는다.
- 생성: 같은 전달 문맥에서 모델 비교. 청킹: 같은 원문·질문에서 청크/근거 회수율 비교. 검색: 같은 청크/정답에서 Dense/Sparse/Hybrid 비교. 리랭킹: 같은 검색 후보 N개와 최종 K에서 off/on 비교.
- 질문별 결과, 실패/누락, cold/warm 지연, 자원 사용, API 비용 또는 미측정 상태를 함께 표시한다. 측정하지 않은 비용을 0으로 보고하지 않는다.
- Faithfulness와 Neutral/Contradiction rate는 실제 생성 입력에 전달된 근거를 기준으로 한다. Correctness P/R/F1은 질문별 승인 GT가 있어야 하며 필수·보충 정책을 계승한다. 새 문서에 GT가 없으면 N/A로 표시한다.
- Recall@K/MRR/nDCG에는 별도 관련성 정답(qrels)이 필요하다. 정답이 없는 임의 문서 실행을 정량 품질 검증 완료라고 표시하지 않는다.
- 근거 후보와 실제 문맥 예산 안에 들어간 청크를 구분한다. top-k, 청크 크기, 모델 입력 토큰 한도를 각각 표시한다.

## 최종 완료의 기준

지원 저장소 링크와 권한을 넣고 공개 모델 또는 본인 API를 선택해 문서→답변을 실행할 수 있다. 청킹/임베딩/검색/리랭커의 지원 옵션을 바꿔 동일 데이터에서 비교 결과를 재현할 수 있다. 가짜 결과·미구현 버튼을 정상 기능처럼 노출하지 않는다. 설치 가이드, 실습 질문, 해석 방법, 제한과 실패 복구가 있고 코딩 도구 양쪽으로 같은 절차를 수행한다. 공개 저장소에 비밀키·실제 비공개 HR 문서·개인 데이터를 포함하지 않는다. main 승격은 별도 명시 요청 사항이다.

P025/P026의 공통 경계와 기본 BM25 문서→답변 연결, P027 저장소 연결은 보류된 평가 모델 실행과 독립인 제품 기반 작업이다. P008 평가 UI/P010 Hybrid/P020 리랭킹의 기존 선행을 자동 해제하지 않는다. 실모델 검증 및 기능별 비교 완료가 남으면 전체 패키지를 완료로 표시하지 않는다.

## Verified increment, 2026-11-27

P024 learning guide: dev 7573c934c76aef493abb6dd1648393c025288d9c. P025 independent LLM adapters/CLI: dev d7406e2b6e2c611cc741ad823d59a90bcefd6043. Both delivered to personal/dev. P025 implements real provider HTTP paths with offline verification; it does not establish live API/model success or RAG integration. P026 completed at dev/personal-dev 0252ec1731431c67172f7692b14fed7ec763821f with 36 offline tests and documented preview integration. P027 is READY for the independent Drive connector increment. P013 model execution remains held.

Hybrid/리랭커 구현 순서 질문은 [미결 결정 기록](reviews/rag-package-order-pending.md)에 보존한다. 답변 전에는 P008/P010/P020 기존 선행을 유지한다.
