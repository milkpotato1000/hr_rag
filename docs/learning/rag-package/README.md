# 공개 모델로 배우는 RAG

[내 파일과 질문으로 시작하기](../../../rag_package/resources/sample/HANDBOOK.md#내-문서와-질문으로-시작하기)에서 PDF·TXT·Markdown을 지정할 수 있습니다. [교육 휴가 PDF 실습](../../verification/p032-s16/README.md)에서는 BM25 첫 청크를 실제 1쪽과 대조했습니다. 같은 한 페이지를 두 가지로 나눴을 때 제1조 제목과 본문이 어디에 남는지도 확인할 수 있습니다. [LLM 청킹 후보와 실제 선택 결과](../../verification/p032-s17/README.md) 같은 입력에서 [허용 후보 번호만 출력하도록 제한한 실험](../../verification/p032-s18/README.md)과 비교할 수 있습니다.

[내 PDF에서 첫 질문하기](../../../rag_package/resources/sample/HANDBOOK.md)에서 독립 폴더에 규정집을 연결하고 BM25 검색부터 로컬 답변·인용 확인까지 진행합니다. [23쪽 규정집의 실제 답변·인용 결과](../../verification/p032-s3/report.html)에서 설치본의 단일 질문 결과를 볼 수 있습니다. 이어서 [같은 PDF의 BM25·Dense·Hybrid와 리랭커 전후 순위](../../verification/p032-s4/README.md)를 비교하세요. [같은 근거에서 로컬 답변과 API 미리보기 읽기](../../verification/p032-s5/README.md)에서는 문맥을 고정하고 생성 단계만 비교합니다.

[같은 PDF의 고정·재귀·구조 청킹 비교](../../verification/p032-s6/README.md)에서 신청 기한과 팀장 승인이 어느 경계에서 끊기는지 확인하세요. 이어서 [규정집 장·절·조항 프로필](../../verification/p032-s7/README.md)에서 같은 근거에 붙은 제목 경로를 비교하세요.

[PDF부터 최종 답변까지 한 번에 실행하기](../../verification/p032-s8/README.md)에서 선택한 구성의 단계별 결과와 PDF 인용 대조를 확인하세요. [학습 UI에서 설정 선택·미리보기·인용 열기](../../verification/p032-s9/README.md)로 같은 실습을 브라우저에서 따라갈 수 있습니다. [설치 화면에서 승인권자 질문에 실제 답변 받기](../../verification/p032-s11/README.md)에서는 질문을 바꾼 뒤 로컬 모델의 답변과 PDF 1쪽을 대조합니다. 같은 설치 구성에서 [규정집에 없는 전기요금 한도를 물은 결과](../../verification/p032-s19/README.md)도 비교하세요.

[저장 실행 두 개 비교하기](../../verification/p032-s12/README.md)에서 고정·재귀 청킹으로 달라진 원문 범위와 실제 질문이 다른 경우의 해석을 확인하세요.

[같은 질문에 대한 고정·재귀 청킹의 실제 Qwen 4B 답변](../../verification/p032-s13/README.md)에서 팀장 승인 문장의 순위와 두 인용 범위를 나란히 읽어보세요.

[검색 구성을 명령으로 선택하기](../../verification/p032-s15/README.md)에서 동일 생성 프로필로 BM25·Dense·Hybrid, 임베딩과 선택 리랭커를 바꾸고 CLI·UI에 연결합니다.

구현과 검증은 Codex 또는 Claude Code에 맡기고, 학습자는 **왜 이 근거가 검색됐는지, 전달 문맥과 답변에서 무엇이 빠졌는지**를 해석합니다. 먼저 모델 호출 없는 샘플 실습을 하고, 저장된 실제 검색 결과를 비교하세요.

## 설치해서 시작하기

1. [현재 설치 안내](install-current.md)에서 새 환경에 wheel을 설치하고 `rag-lab init`으로 독립 실습 폴더를 만듭니다. 이 폴더에 생성된 `START_HERE.md`가 실행 순서입니다. `hr_rag_dev`나 plan/dev 하네스 설치는 필요하지 않습니다.
2. 그 폴더에서 `doctor` → `snapshot` → 규칙 청킹·BM25 `build/ask/compare` preview를 실행합니다. 샘플 모델의 `needs_configuration`은 예상 상태입니다. preview는 답변을 생성하지 않습니다.
3. generation-setup으로 사용할 로컬 또는 API 모델을 지정합니다. 임베딩·리랭커는 [공개 모델 준비](model-preparation.md) 경로를 사용합니다. 설정 생성, 파일 준비, 실제 추론, 품질 검증은 서로 다른 단계입니다.
4. [일반 문서 CLI](document-rag.md) → [다섯 청킹 방식](model-chunking.md) → [Hybrid 검색](hybrid.md) → [선택 리랭커](reranking.md) 순서로 연결을 익힙니다. [학습 UI](ui.md)에서도 같은 코어와 저장 결과를 볼 수 있습니다.
5. [S1 검색·리랭킹](live-retrieval-s1.md)과 [S2b 청킹 비교](chunk-comparison-live.md)를 읽고, [실험 질문과 기록 양식](experiments.md)으로 한 조건씩 비교합니다. 실제 모델을 다시 실행할 필요 없이 결과를 해석할 수 있습니다.

이 경로의 [최신 문서·core-only 설치 검증](../../verification/p032-s2c/README.md)은 모델 호출 0회입니다. PDF에는 선택 PDF 의존성이, Dense/Hybrid·의미 청킹·리랭커에는 고정 retrieval SDK와 모델 파일이 필요합니다. `doctor`의 설정·설치 metadata 확인은 모든 파일 hash, 실제 SDK import, 모델 실행 성공을 보장하지 않습니다.

## 로컬 공개 LLM과 선택 유료 API

실습 폴더에서 모델명을 지정하면 프로필과 BM25 검색 설정을 함께 만듭니다. 아래 API 예제의 YOUR_MODEL_ID는 본인 계정의 모델명으로 바꾸세요.

```sh
rag-lab generation-setup --provider ollama --model qwen3:4b --out my-local
rag-lab generation-setup --provider openai_chat --model YOUR_MODEL_ID --key-env OPENAI_API_KEY --out my-api
```

원하는 설정의 출력에서 `commands.pipeline_preview`와 `commands.serve`를 따라가세요. 기본 로컬 설정은 네트워크 없이 만들 수 있고, 설치된 모델을 확인해 생성용으로 구성할 때는 새 출력 경로와 --inspect-local을 사용합니다. 기존 사용자 spec과 혼합 역할 설정에는 llm-configure를 사용하세요. [설치 실습과 두 코딩 도구용 요청](../../../rag_package/resources/sample/HANDBOOK.md) · [독립 설치 검증 결과](../../verification/p032-s14/README.md)

```text
문서 snapshot → 청킹 → BM25 / 공개 임베딩 Dense·Hybrid
                              ↓
                 검색 후보 → 선택 공개 리랭커
                              ↓
                     전달 문맥 선택·기록
                              ↓
                  답변 LLM: 로컬 / 선택 API
                              ↓
                       답변 + 원문 인용
```

API 선택은 LLM 역할만 바꾸며 임베딩·리랭커는 공개 모델을 유지합니다. LLM 청킹은 별도 `chunking` 역할입니다. `evaluation` 역할을 지정해도 평가기가 실행되지는 않으며 현재 평가 실험은 보류입니다. 기본 실습의 필수 단계가 아닙니다.

실제 답변을 생성하려면 모델 identity·provider 설정과 문서 전송 범위·호출 상한을 확인하고, 생성한 설정을 RAG config의 `llm_config`로 연결한 뒤 `ask --execute`를 명시합니다. UI에서는 서버의 `--allow-model-execution`과 화면의 실행 선택이 필요합니다. 검색·리랭킹·청킹의 실행 옵션은 각각 별도입니다. 기본 preview에 이 옵션들을 자동으로 추가하지 않습니다. [provider 안내](providers.md)와 [실행 CLI](document-rag.md)를 따르세요. [로컬 4B 첫 실제 생성](local-generation-s2d.md)은 출력 상한에서 중단되어 유효 답변을 얻지 못했습니다. 유료 API·LLM 청킹·개인 Drive 연결은 아직 실서비스 검증 전입니다.

## 저장 결과로 배우기

| 자료 | 관찰할 내용 | 검증 범위 |
| --- | --- | --- |
| [S1 검색·리랭킹](live-retrieval-s1.md) | 검색 5설정 × 10질문 = 50행, none 포함 리랭킹 3방식 × 10질문 = 30행 | 고정 가상 규정집·CPU의 실제 E5/BGE 검색 및 두 리랭커. mMiniLM 최초 실패도 보존 |
| [S2a 경계 준비](chunk-boundaries-s2a.md) | 규칙 청크와 의미/LLM unit·window preview | 모델 0회. 경계 포함 관찰이며 검색 품질 점수가 아님 |
| [S2b 청킹 비교](chunk-comparison-live.md) | 고정·재귀·구조·E5 의미 4방식 × 10질문 = 40검색 | 같은 원문·E5 Hybrid. 전달 문맥 필수 fact는 각각 27/29/29/29개(분모 38). 답변 생성 0회 |
| [S2d 로컬 생성](local-generation-s2d.md) | 저장 문맥으로 Qwen4B 실제 생성1회 | 첫 문항 출력 상한 도달로 중단. 유효 답변0·나머지9문항 미실행 |
| [로컬 Thinking 모델 검증](local-generation-s2e.md) | 같은 생일휴가 질문·근거로 4B 생성 1회 | 최종 답변, 인용, 필수 조건을 원문과 대조하는 실습 |
| [로컬 구조화 출력과 인용 대조](../../verification/p032-s2f/report.html) | 같은 4B·질문·문맥에서 출력 형식만 변경 | 첫 유효 답변. 인용 3개는 원문과 일치했지만 수습 제외가 본문에서 누락되어 필수 조건 5/6 |
| [조건·예외 지시 변경 전후](../../verification/p032-s2g/report.html) | 같은 질문·청크·모델에서 시스템 지시만 변경 | 수습 제외 복원. 신청 기한과 승인 요건의 구분이 흐려져 후속 9문항 미실행 |
| [생일휴가 답변 지시 세 버전 비교](../../verification/p032-s2h/report.html) | 같은 청크·4B 설정에서 행위별 기한 지시 추가 | 출력 4,096토큰에서 잘려 유효 답변 없음. 새 지시의 의미 정확성은 평가 불가 |
| [첫 창의 실제 LLM 청킹 진단](../../verification/p032-s2i/report.html) | 규정집 원문 762자·20개 후보 단위에서 Qwen 4B가 경계 선택 | 출력 상한에서 잘림. 유효 경계 없음, 나머지 33개 창 미실행 |
| [청킹 ID를 창별 번호로 바꾼 결과](../../verification/p032-s2j/report.html) | LLM 청킹 설정에 `"id_representation": "window_number"`를 추가. 생략하면 기존 영속 ID 사용 | 전체 입력 2,171→1,037토큰, 두 실행 모두 출력 상한 도달. 실제 경계 품질 미측정 |
| [S2b 최초 중단](chunk-comparison-s2b.md) | 환경 오류, 미실행·미확정과 복구 조건 | 실패를 삭제하거나 0점 품질 결과로 바꾸지 않음 |

S2b의 의미 방식은 후보 20개에서 38/38 fact를 찾았지만 최종 문맥에는 29/38을 전달했습니다. 경계 249개는 모두 최대 길이 조건으로 결정됐으므로 “의미 경계가 우수하다”고 결론내릴 수 없습니다. fact가 있는 질문은 8개, 없는 2개는 N/A입니다. 새 청크 qrels가 없어 Recall/MRR/nDCG도 N/A입니다. 작은 학습 세트 관찰을 일반 한국어 품질이나 다른 환경의 성능으로 확대하지 않습니다.

## 코딩 도구에 맡기기

설치 후 만든 독립 실습 폴더를 두 도구에서 공통으로 사용합니다. 그 폴더와 상위의 기존 AGENTS.md/CLAUDE.md 규칙을 존중하세요. init은 Git·하네스·코딩 도구를 설치하지 않습니다. 이 저장소에 기여할 때는 별도로 저장소의 plan→dev 규칙을 따릅니다.

Codex에 요청:

> 현재 폴더와 상위 AGENTS.md를 확인하고 START_HERE.md의 모델 없는 preview를 끝까지 실행해줘. 원문→청크→검색 후보→전달 문맥을 설명하고, 내가 예상할 변화와 확인할 지표를 제시해줘. 기존 산출물은 보존하고 새 출력 경로를 사용해줘. 모델·API·Drive 호출이나 다운로드·서버 시작은 하지 마.

Claude Code에 요청:

> 현재 폴더와 상위 CLAUDE.md/AGENTS.md를 확인하고 START_HERE.md의 같은 rag-lab preview를 실행해줘. 청킹 방식 하나를 바꾼 결과와 누락된 근거를 대조하고, 미측정 지표는 N/A로 설명해줘. 실제 모델·API·Drive 호출이나 다운로드·서버 시작은 하지 마.

두 요청은 공통 CLI 실습 예시이며 두 제품 UI에서 직접 실행해 검증했다는 뜻은 아닙니다.

## 참고와 이력

- [모델과 지원 상태](models-and-support.md), [Drive 단일 문서 연결](drive.md): 구현 지원과 실제 검증 범위를 구분합니다.
- [기존 Naive RAG](<../../../1. Naive RAG/LEARNING_GUIDE.md>)와 [LangChain 비교](<../../../1. Naive RAG/variants/langchain/README.md>), [기존 장문 PDF 청킹 단계](<../../../2. Document Chunking/LEARNING.md>): 각 corpus·버전의 역사적 실습입니다. 새 패키지 snapshot과 자동으로 같은 입력이 되지 않습니다.
- P024의 [local 설계 JSON](examples/local.json) / [API 설계 JSON](examples/api.json)은 `example_only`인 역사 참고이며 실행 CLI 설정이 아닙니다. 현재 설치 실습은 generation-setup에서 시작합니다.
- [P013 보류 기록](../../verification/p013/recovery-20261127/README.md): 평가 실험은 재개하지 않았습니다. [로드맵](../../planning/rag-package-roadmap.md)의 미완료 단계와 브라우저 파일 선택창 검증도 남아 있습니다.
