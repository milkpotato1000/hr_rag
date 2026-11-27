# 모델 후보와 현재 지원 범위

[학습 시작점](README.md)으로 돌아가기. 기준일: 2026-11-28. 후보 선정과 실행 검증은 구분합니다. 이 목록은 인기 순위표가 아니며, 새 모델을 설치하는 명령도 아닙니다.

## 역할별 후보

| 역할 | HF 원본 후보·공식 모델 카드 | 라이선스 표시 | 프로젝트에서 확인한 범위 |
| --- | --- | --- | --- |
| 생성·LLM 평가 | [Qwen/Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) | Apache-2.0 | 기존 Ollama 8B 평가 실험 이력 있음. P013 첫 추출 성공 후 OS 메모리 critical로 중단. 전체 평가 품질·안전한 연속 실행 미검증, 현재 보류 |
| 기존 생성 기준선 | Qwen3-4B-Thinking-2507 계열 | 잠금 파일에 Apache-2.0 | 로컬 태그 qwen3:4b의 저장된 model_info는 Thinking/2507. 기존 Naive·LangChain 실행 검증 범위만 인정 |
| 임베딩 | [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) | MIT | 기존 Ollama bge-m3:567m 기반 Dense 검색 검증 이력. HF 원본의 모든 검색 모드를 구현했다는 뜻은 아님 |
| 임베딩 대안 | [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) | MIT | HF adapter·tiny SDK 시험 완료, 사전학습 한국어 품질 미검증 |
| 리랭커 | [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | Apache-2.0 | 실제 CrossEncoder adapter·tiny SDK·설치/UI 검증. 한국어 사전학습 품질 미검증 |
| 리랭커 대안 | cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 | Apache-2.0 | 같은 CrossEncoder 연결 검증 범위. 한국어 실모델 미검증 |
| NLI | P014의 후속 다국어 후보 | 실행 계약에서 확인 예정 | 선택 비교 실험. 현재 기본 실행 필수 모델 아님 |

네 HF 링크는 기준일에 공식 카드를 열어 라이선스와 역할을 확인했습니다. E5는 모델 카드의 query/passage 입력 정책을 따라야 합니다. 모델을 바꾸면 접두어, 정규화, 길이·truncation 정책도 비교 기록에 포함합니다. 리랭커 raw score를 다른 모델의 같은 숫자와 동등한 확률로 해석하지 않습니다.

HF ID는 원본 저장소 식별자이고 Ollama 태그는 실행 환경의 이름입니다. 태그만 같아도 같은 가중치라는 보장은 없습니다. 실제 실행에는 원본 revision, 변환·양자화 방식, 파일 digest, tokenizer/chat template, runtime 버전과 입력 설정을 고정합니다. [기존 생성 잠금](<../../../1. Naive RAG/variants/langchain/generation-lock.json>), [기존 검색 runtime 잠금](<../../../2. Document Chunking/runtime-lock.json>), [8B 모델 잠금](../../verification/p019/model-lock.json)을 비교해 보세요.

공개 가중치는 공개된 범위와 라이선스 조건을 확인해야 하며 “공개”라는 말만으로 완전한 오픈소스 또는 무제한 재배포를 의미하지 않습니다. 후보 확정 시 공식 배포 여부·라이선스·한국어 성능·메모리·런타임 호환성을 함께 검토합니다. HF 다운로드/좋아요를 인기도 근거로 쓰려면 지표 종류·집계 시점도 남기며, 인기 순위를 우리 문서의 정답률로 바꾸어 설명하지 않습니다.

## 현재 쓸 수 있는 기능과 후속 기능

| 구분 | 기능 | 근거·제한 |
| --- | --- | --- |
| 기존 구현 | BM25 / 고정 BGE Dense 검색, Qwen 생성·인용, Direct/LangChain 비교 | [Naive 안내](<../../../1. Naive RAG/README.md>), [P011 채택 결과](../../verification/p011/adoption-decision.json). 모든 질문의 완전한 답변을 보장하지 않음 |
| 기존 구현 | 장문 가상 PDF, 추출, 5종 청킹, BM25/Dense 비교·문맥 시뮬레이션 | [청킹 안내](<../../../2. Document Chunking/README.md>). 규칙·의미·LLM 청킹의 호출 조건이 서로 다름 |
| 설정 예시만 제공 | local/api 공통 JSON, 생성·평가 역할별 선택 | [local](examples/local.json) / [api](examples/api.json). example_only=true, 실제 CLI 스키마 아님 |
| 일부 구현·미완료 | claim 추출·판정·Python 집계와 실제 RAG 평가 연결 | [평가 모듈](../../../evaluation/project_b/README.md). 오프라인 모듈 검증과 전체 모델 검증은 별개. P013 BLOCKED |
| 독립 구현·오프라인 검증 | Ollama/OpenAI Chat/Anthropic Messages adapter와 CLI | [provider 안내](providers.md). 실제 호출·기존 HR UI/평가 runner 연결 미검증 |
| 신규 구현·오프라인 E2E 검증 | 일반 PDF/TXT/MD snapshot·규칙3종·BM25·선택 LLM·원문 인용·비교 CLI | [일반 문서 안내](document-rag.md). 실모델/실 API/개인 문서 품질 미검증 |
| 후속 계획 | 임의 임베딩 교체, Qwen instruction 리랭커 | [로드맵](../../planning/rag-package-roadmap.md). 새 범용 UI는 등록 API 설정 선택을 지원하며 실제 호출 품질은 미검증 |
| 신규 구현·오프라인 검증 | Google Drive 단일 파일 REST/OAuth→snapshot | [Drive 안내](drive.md). 실제 계정 미검증. 명시 재수집/rebuild 지원, 폴더·자동 동기화는 후속 |
| 신규 구현·독립 설치 검증 | wheel/sdist·rag-lab·init/doctor·샘플 preview | [설치 안내](install.md). 같은 Mac 새 venv/core·extras·재빌드 검증. 다른 OS/두 제품 UI/실서비스 미검증 |
| 구현·부분 브라우저 검증 | [통합 학습 UI](ui.md) | 합성 backend·설치 wheel 검증. 파일 선택창 정책 차단으로 C4 미완료, 실모델 품질 비교는 후속 |

## 메모리와 운영 상태

모델 파일 용량과 실행 메모리는 다릅니다. 가중치 외에도 문맥 길이에 따른 캐시와 런타임 메모리가 필요합니다. M1 16GB에서 여러 모델을 동시에 올려도 안전하다고 가정하지 않습니다. 8B 한 요청의 응답 성공은 전체 실험의 메모리 안전을 의미하지 않습니다.

기존 [P013 자원 중지 기록](../../verification/p013/resource-stop.json)에는 OS critical 관측이 있습니다. [재개 사전 점검](../../verification/p013/recovery-20261127/runtime-unreachable.json)은 loopback 연결 거부였고 새 모델 요청 0회였습니다. 이후 사용자가 P013을 보류했습니다. 이 문서는 서버 복구·모델 재실행·재개 권한 소비를 요청하지 않습니다. 모델 순차 실행도 별도 재개 계약과 실제 관찰을 통과해야 합니다.

범용 경로의 E5-small/BGE-M3 Dense와 Hybrid RRF는 [새 검색 안내](hybrid.md)를 따릅니다. 두 catalog 선택·실제 SDK 연결은 구현했으며 사전학습 가중치와 한국어 품질은 미검증입니다.

P010 [Hybrid](hybrid.md)와 P020 [고정 후보 리랭킹](reranking.md)은 실제 SDK 경로·설치·합성 비교 화면을 검증했습니다. 기존 P029 파일 업로드 검증의 차단은 별도로 유지합니다.
