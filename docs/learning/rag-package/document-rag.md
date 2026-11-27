# 일반 문서로 RAG 연결하기

P026에서 **로컬 PDF/TXT/Markdown → snapshot → 규칙 청킹 → BM25 → 선택 LLM → 원문 인용**을 연결했습니다. P025의 Ollama·OpenAI Chat·Anthropic Messages adapter를 사용합니다. 검증은 합성 문서·기존 가상 PDF·가짜 응답/HTTP 서버로 수행했습니다. 실제 모델 품질·메모리·유료 API·개인 문서는 검증하지 않았습니다. P013은 계속 보류합니다.

[학습 시작점](README.md) · [LLM 설정](providers.md) · [비교 질문과 지표 해석](experiments.md) · [검증 기록](../../verification/p026/README.md)

## 준비와 지원 범위

Python 3.10+가 필요합니다. TXT/Markdown·청킹·BM25는 표준 라이브러리만 사용합니다. PDF는 선택 의존성 pypdf==6.21.2가 필요하며 [고정 pin/hash](../../../rag_package/requirements-pdf.lock)를 제공합니다. PDF 의존성이 없으면 PDF 경로는 needs_review이고 텍스트 경로는 계속 사용할 수 있습니다. 이번 검증은 기존 Python 3.12.14/pypdf 환경을 재사용했으며 새 설치를 하지 않았습니다.

아래 `python3`는 Python 3.10+ 실행 파일을 뜻합니다. 이 저장소의 기존 검증 환경에서는 `'2. Document Chunking/.venv/bin/python'`으로 바꾸어 실행할 수 있습니다. 새 환경에서 PDF 의존성을 설치할 때의 명령은 `python3 -m pip install --require-hashes -r rag_package/requirements-pdf.lock`입니다. 설치가 필요한 시점에만 별도로 실행하며 이번 문서 실습에서는 다운로드하지 않습니다.

| 구성 | 현재 새 경로에서 지원 | 아직 지원하지 않는 기능 |
| --- | --- | --- |
| 입력 | 명시한 로컬 PDF/TXT/MD 파일 목록, 다중 문서; [Drive connector](drive.md)의 단일 문서 snapshot | 폴더 동기화, OCR, 암호 PDF, 표 구조 복원 |
| 청킹 | fixed / recursive / structure 및 [semantic / LLM](model-chunking.md) 저장 경계 | 임의 모델/custom code |
| 검색 | BM25, [Dense/Hybrid](hybrid.md), 별도 [고정 후보 리랭커](reranking.md) | 임의 모델/custom code |
| 생성 | P025 generation 역할, json_object 응답 | 기존 HR UI·평가 runner로의 자동 연결 |
| 비교 | 기존 설정 2~4개, v3 저장 청크 2~5개 비교, 기본 preview | 정답 없는 품질 점수 자동 산출 |

미지원 옵션은 오류이며 BM25나 다른 모델로 조용히 대체하지 않습니다. 기존 [P007 청킹 실습](<../../../2. Document Chunking/LEARNING.md>)의 다섯 방식은 별도 구현으로 보존되어 있습니다. 새로운 경로의 지원 범위와 혼동하지 마세요. 디렉터리 공개는 OS의 원자적 no-clobber 기능을 사용합니다. 현재 macOS에서 검증했고 Linux는 대응 renameat2 경로가 있으나 미검증이며, 해당 기능 없는 환경은 명확히 실패합니다. [wheel 설치 실습](install.md)은 같은 Mac 새 venv에서 검증했습니다. 다른 컴퓨터/OS는 미검증입니다.

## 모델 호출 없이 끝까지 관찰하기

모든 명령은 `hr_rag_dev/` 루트에서 실행합니다. [샘플 sources](../../../examples/rag/sources.json)는 가상 문서 두 개를 가리킵니다. 아래 출력 경로가 이미 있으면 새 이름을 사용하세요. `.rag-runs/`는 Git에서 제외되며 결과를 덮어쓰지 않습니다.

```sh
python3 -m rag_package snapshot --sources examples/rag/sources.json --out .rag-runs/sample-snapshot
python3 -m rag_package build --snapshot .rag-runs/sample-snapshot --config examples/rag/fixed.json --out .rag-runs/sample-fixed
python3 -m rag_package ask --run .rag-runs/sample-fixed --config examples/rag/fixed.json --question '생일 휴가 자격과 사용 기간은?' --out .rag-runs/sample-preview
python3 -m rag_package compare --snapshot .rag-runs/sample-snapshot --configs examples/rag/fixed.json examples/rag/recursive.json examples/rag/structure.json --questions examples/rag/questions.json --out .rag-runs/sample-comparison
```

ask와 compare는 기본이 **preview**입니다. 키 조회·모델/API 요청 없이 후보, 전달 예정 근거, 제외 이유와 실제 wire messages/hash를 기록합니다. `comparison.json`과 `comparison.md`에는 모든 질문×설정 행, 바뀐 축, 오류와 보류가 있습니다. 우주선 질문처럼 근거가 없으면 preview에서도 abstained이고 생성 요청은 0입니다.

PDF를 확인하려면 첫 명령의 sources만 [sources-pdf.json](../../../examples/rag/sources-pdf.json)으로 바꾸고 새로운 출력 경로를 사용하세요. 저장소의 기존 23페이지 가상 규정집을 읽습니다. 이후 build/ask에 새 snapshot 경로를 명시합니다.

## 원문·청크·인용의 연결

sources의 schema_version은 1이며 documents 각 항목에 document_id/title/path/format/synthetic를 적습니다. path는 sources 파일 위치 기준입니다. ID는 영문·숫자로 시작하고 영문·숫자·밑줄·하이픈으로 구성한 최대 80자입니다. 실제 문서는 synthetic=false로 표시합니다. snapshot은 원본 bytes를 복사하고 절대 원본 경로를 manifest에 넣지 않습니다.

PDF는 물리 페이지, TXT/Markdown은 논리 페이지 1입니다. 페이지별 raw text와 NFC/LF 정규화 text를 구분하고, 페이지 사이 LF 두 개는 어느 페이지의 원문에도 속하지 않습니다. canonical start/end는 Unicode 문자 위치이며 토큰이나 PDF 좌표가 아닙니다. 원본·페이지·canonical의 hash와 페이지 재구성을 소비 시 검증합니다. snapshot을 만든 뒤 원본을 바꿔도 기존 snapshot은 그대로이며 새 내용을 반영하려면 새 snapshot/build가 필요합니다.

| 방식 | 경계를 정하는 규칙 | 오버랩 |
| --- | --- | --- |
| fixed | 최대 size_chars 길이의 이동 window | 다음 시작을 overlap_chars만큼 앞당김 |
| recursive | 문단 → 문장 → 공백 → 강제 길이 경계 | base 최대 size-overlap, 왼쪽 확장 후 최종 size 이하 |
| structure | Markdown ATX 제목·한국어 제N장/제N조 휴리스틱, 긴 섹션은 recursive | 같은 섹션 시작을 넘지 않음 |

제목을 못 찾으면 structure의 detection 기록에 recursive fallback 이유를 남깁니다. 이 fallback은 구조 탐지 정책이며 검색기나 provider의 자동 변경과 다릅니다. 모든 원문 범위를 덮되 공백뿐인 청크는 검색에서 제외하고 coverage에 기록합니다. 문서끼리는 합치지 않습니다. heading_path는 표시 metadata이며 검색 text와 quote에 덧붙이지 않습니다.

청크 크기는 100..4000자, 오버랩은 0..min(400,size-1), top_k는 1..100, 문맥 예산은 1..64000자입니다. top_k 후보에서 청크 전체가 남은 예산에 들어가면 전달하고, 안 들어가면 excluded=budget로 기록한 뒤 다음 후보를 봅니다. 청크를 잘라 끼워 넣지 않습니다. 문자 예산에는 프롬프트·JSON overhead가 포함되지 않으며 모델의 토큰 한도를 보장하지 않습니다.

BM25는 NFKC/casefold 단어 토큰을 사용하며 한국어 형태소 분석을 하지 않습니다. 단어 형태가 달라 누락되는 사례를 관찰하세요. 동점은 chunk ID 순서이고, title/정답/답변은 검색 점수에 들어가지 않습니다.

## 모델을 바꾸는 지점

[RAG 설정 예시](../../../examples/rag/fixed.json)의 llm_config는 별도 P025 JSON을 가리키며 상대 경로는 RAG 설정 파일 기준입니다. generation 역할의 response_mode=json_object가 필수입니다. evaluation 역할은 호출하지 않습니다. API로 바꾸려면 별도의 설정 사본에서 llm_config와 검증된 provider/model을 지정합니다. 임베딩과 리랭커를 LLM API로 바꾸는 설정은 아닙니다.

LLM·top_k·문맥 예산만 바꾸면 청크/index identity는 유지됩니다. 청킹 설정이나 검색 방법이 기존 build와 다르면 stale 오류이며 자동 재생성하지 않습니다. 청킹/원문 변경에는 새 build를 만드세요. compare는 확인한 설정을 실행 폴더에 고정하고 같은 source/questions hash로 모든 행을 기록합니다.

실제 호출은 ask/compare에 `--execute`를 명시한 경로로 구현되어 있습니다. 이 문서의 기본 실습에는 붙이지 않습니다. 실문서 전송·키·모델·비용/호출 상한·중지 조건은 실제 실행 전에 별도로 정해야 합니다. P013을 이 CLI로 재개하지 마세요. compare의 생성 요청 상한은 질문 수×설정 수, 최대 80회이고 자동 재시도는 없습니다. preview summary에 선택 provider/model, 문맥과 상한이 표시됩니다.

모델의 JSON은 status/answer/citations만 허용합니다. answered는 전달된 chunk_id를 중복 없이 한 개 이상, abstained는 빈 인용을 요구합니다. quote/page를 모델이 만들어 보내면 허용하지 않습니다. 코드가 검증된 canonical slice와 문서·페이지·제목 경로를 연결합니다. **인용이 유효하다는 것은 답변 의미까지 참이라는 판정이 아닙니다.**

## 결과와 오류를 읽기

`result.json`에는 source/chunk/index/config/query/messages hash, 후보·전달·제외, provider identity/status/usage, 단계별 지연, dispatch_attempted와 citation_validation이 있습니다. execution_kind는 preview/live/test_fixture이며 주입 transport는 자동 test_fixture입니다. provider 응답의 raw body·hidden thinking·인증 정보와 업무 schema를 통과하지 않은 content는 정상 답변에 저장하지 않습니다. 정상 messages/answer에는 원문이 포함될 수 있으므로 산출물은 개인 자료로 취급하세요.

| 상황 | 결과와 다음 확인 |
| --- | --- |
| 빈/스캔 페이지·손상/암호 PDF | needs_review. ready build 금지. PDF 원문/추출 가능 여부 확인; OCR은 별도 작업 |
| PDF 의존성 없음/버전 불일치/30초 초과 | 명확한 reason. 텍스트 경로는 독립 사용 가능 |
| snapshot/index 변조 또는 청킹 설정 불일치 | stale 오류. 원본 artifact 보존 후 올바른 새 snapshot/build 선택 |
| 검색 근거 없음/모두 예산 제외 | 모델 호출 0, abstained. 검색 후보와 문자 예산 확인 |
| 모델 실패·절단·거절·JSON/인용 오류 | failed stage/code 및 전송 여부 기록, 정상 답변으로 표시하지 않음 |
| 호출 후 결과 저장·출판 실패 | dispatch_attempted 보존, 자동 재호출 없음. 이미 처리/과금됐을 수 있으므로 기록·출력 경로부터 확인 |

입력은 문서 20개, 파일당 20MiB, PDF 100페이지/30초, canonical 문서당 100만자·전체 200만자까지입니다. 큰 파일/잘못된 UTF-8/중복 ID/불필요 옵션을 거부합니다.

Faithfulness는 evaluator_not_connected, Correctness와 Recall/MRR/nDCG는 ground_truth_not_configured로 null입니다. 실패를 0점으로 바꾸지 않습니다. 비용은 null/unmeasured이며 누락 usage도 0이 아닙니다. 같은 문맥에서 모델을 비교할 때와 청킹을 바꿔 검색부터 비교할 때는 바뀐 조건이 다르므로 한 축씩 변경하고 변경축 표를 확인하세요. 파싱/청킹/검색/생성 지연도 별개로 봅니다.


다섯 방식의 저장 경계 생성·재생·파생·원문 fact 비교는 [모델 청킹 실습](model-chunking.md)을 참고하세요. 의미/LLM 청킹은 등록 설정과 별도 실행 권한으로 연결되며 실제 한국어 모델 품질은 미검증입니다.
