# Document Chunking — 원문·청킹·검색 비교

현재 장문 실습 입력은 **source-v4 단일 규정집**입니다. 아래 source-v3 설명은 보존된 짧은 기준선입니다.


## P007 실습 실행

P017부터 방식은 드롭다운, 크기·오버랩·의미 거리 임계값은 직접 입력합니다. 각 입력 아래의 추천값은 학습 출발점이며, 허용 범위는 실행 보호 한도입니다. A/B는 위에서 생성한 성공 저장 이력에서만 고르고 선택한 검색기의 색인을 먼저 준비합니다. 기존 P007 고정 실험은 이력에 별도 출처로 표시됩니다.

문자 예산은 **1~24,000자, 기본8,000자**입니다. Top-K(1~20개)는 결과 카드/평가 범위이고, 문자 예산은 별도로 상위20 후보에서 통째 청크를 고르는 시뮬레이션입니다. 선택·제외 내역을 펼쳐 확인할 수 있습니다. 모델의 토큰 한도나 청크 한 개의 길이가 아닙니다.

사용자 설정 CLI는 JSON 파일을 `--config`로 전달합니다. 예를 들어 `{"method":"fixed","size_chars":600,"overlap_chars":100}`를 `runs/custom.json`에 저장한 다음 `--config runs/custom.json --output-dir runs/custom-example`로 실행합니다. semantic은 `distance_threshold`도 필요합니다. API와 동일한 검사·정규화·설정 ID를 사용합니다. LLM의 새 실행은 새 경계를 생성하며, 같은 설정의 저장 결과 재생과 구분합니다. 기존 누적 자원 예산을 계속 사용합니다.

다섯 청킹 방식·14설정과 BM25/Dense 검색 비교를 구현했습니다. 학습 순서는 [LEARNING.md](LEARNING.md)를 따르세요.
원문은 아래 P016에서 확정한 PDF/추출본을 그대로 사용합니다. 전체 실험은 `artifacts/experiment-002/`, 최초 실패는 `artifacts/experiment-001/`에 보존했습니다.
후속 후보는 tuning으로 고정한 `structure-0`이며 holdout을 보고 재선정하지 않았습니다.

이 단계 폴더에서 Python3.12.14로 별도 환경을 만들고 고정 해시 의존성을 설치합니다. 기존 소유 Ollama0.40.8의 Qwen3:4b/BGE-M3만 사용합니다. 서버가 모델을 다운로드하거나 기존8001서버를 재시작하지 않습니다.

```sh
uv venv --python 3.12.14 .venv
uv pip install --python .venv/bin/python --require-hashes -r requirements-langchain.lock -r ingestion-requirements.lock
.venv/bin/python scripts/serve_chunking.py --port 8003
```

`http://127.0.0.1:8003/`에서 원문 페이지 → 설정/저장 결과 → 색인 준비 → 같은 질문 A/B를 사용합니다.
GET/설정변경은 모델을 호출하지 않습니다. **새로 실행**은 새 invocation이며, 저장 결과 보기는 모델 호출0회입니다.
미리보기23장은 검증된 P016 PNG 사본으로 런타임 PDF 렌더러 없이 동작합니다.
`.runtime/`의 영구 ledger·cache·index·job은 Git에서 제외됩니다. 다른 폴더로 옮겨 실험할 때 ledger를 초기화해 예산을 우회하지 마세요.
완료 실험의 사용량과 호출 기록은 verification 및 experiment artifact에도 보존합니다.

CLI 예시(출력 경로는 새 폴더여야 함):

```sh
mkdir -p runs
.venv/bin/python scripts/chunk_documents.py --documents data/source-v4/extracted/manifest.json --config fixed-400-80 --output-dir runs/fixed-example
.venv/bin/python -m unittest discover -s tests -v
```

고정 전체 실험 실행기는 `scripts/run_chunking_experiment.py`입니다. `--spec experiments/p007/spec.json --output-dir <새폴더> --llm-runs <독립3회 run ID>`를 요구합니다. 기존 실행은 저장 결과로 관찰하는 것이 기본이며 전체 재실행에는 남은 누적 예산 확인이 필요합니다. 답변 생성/LLM 평가기는 이 단계에 포함하지 않았습니다.

## P016 단일 장문 규정집

`data/source-v4/authoring/hr-handbook.md` 하나를 작성해
`data/source-v4/output/pdf/hr-handbook.pdf` 하나로 출력했습니다.
23페이지, 본문35,477자, 6장·15절·57조항·105문단입니다.
장별 본문은 생일3,275 / 연차7,515 / 재택6,650 / 복지5,237 / 교육5,515 / 출장7,285자입니다.
길이는 토큰 수가 아니며 제목·목차·작성 주석을 제외하고 본문 공백을 포함한 NFC/LF Unicode 문자 수입니다.
`length-accounting.json`에 포함/제외 원문 범위가 있습니다.

기존31개 정책은 보존하고, 추가 가상 처리 절차481문장과 설명14문장을 분류했습니다.
새 권리/지급액/신청 자격을 만들지 않았고 시행일은 여전히 미정입니다.
전체가 가상 자료이며 사람 승인 정답이나 실제 회사 규정은 아닙니다.

- `extracted/canonical/hr-v4-handbook.txt`: 한 문서의 연속 텍스트. 페이지 footer도 보존합니다.
- `extracted/manifest.json`: 원본/페이지 hash, 연속 offset, 고정 pypdf6.21.2.
- `section-map.json`: 제목→장→절→조항 계층과 본문/정확 인용 위치. 목차 항목은 실제 제목과 분리합니다.
- `policy-inventory.json`, `policy-map.json`: 모든 본문 문장 분류와 v3의31주장/34본문 출현 대응.
- `corpus-profile.json`: 분량·짧은/긴 조항·참조·페이지 횡단·중복 후보. 페이지를 넘는 문단17개입니다.
- `authoring-review.json`: 모든 조항/문단의 직접 서술 검토 및 절차·예외 연결.
- `handoff-manifest.json`: 파일 hash와 원문 commit, 외부 완료 기록 연결.

수집 대상은 PDF 한 개뿐이며 문서 ID는 `hr-v4-handbook`입니다. 장별 ID는 section ID입니다.
페이지를 넘는 정확 인용에는 footer가 끼어 있을 수 있습니다. `excluded_footer_spans`는 그 위치를 명시하며
canonical을 조용히 정리하거나 제목을 각 문단에 복제하지 않습니다.

단계 폴더에서 다음처럼 새 출력 위치를 사용합니다. `runs/`는 먼저 만듭니다.

```sh
.venv/bin/python scripts/validate_handbook.py --source-root data/source-v4
.venv/bin/python scripts/snapshot_drive_fixture.py --catalog data/source-v4/drive-fixture-catalog.json --output-dir runs/v4-snapshot-01
.venv/bin/python scripts/ingest_documents.py --manifest runs/v4-snapshot-01/manifest.json --output-dir runs/v4-extracted-01
.venv/bin/python scripts/prepare_handbook.py --source-root data/source-v4 --output-dir runs/v4-maps-01
python3 scripts/create_handbook_pdf.py --font /System/Library/Fonts/Supplemental/AppleGothic.ttf --output-dir runs/v4-pdf-01
```

작성 도구만 ReportLab/로컬 글꼴이 필요합니다. 수집·추출·검증은 고정 pypdf와 표준 라이브러리만 사용하며
독립 복사해 실행할 수 있습니다. `prepare_handbook.py`는 전체 원문·추출 결과와 검토 자료에서 지도 파일을 재계산합니다.
동결 manifest는 원문/도구를 커밋한 뒤 `--freeze-source-commit <full SHA>`로 별도 새 폴더에 만들며
자기 hash는 외부 완료 증거에 기록합니다. 이미 존재하는 출력은 도구가 덮어쓰지 않습니다.

P016 완료 당시에는 원문 준비까지 수행했습니다. 이후 P007에서 새 고정 계약(630단위/35window/38질문)으로 청킹·검색 실험을 완료했습니다. 기존 UI와8001서버의 기본 corpus는 유지합니다.

## 보존된 P015 기준선

P015에서 준비한 가상 HR 규정 원문입니다. 현재 범위는 PDF 작성, 로컬 수집 fixture,
텍스트 추출 및 정책 보존 대조까지였습니다. 아래 설명은 P015 당시의 원문 준비 범위입니다. 현재 청킹·검색·모델 호출·웹 화면은 위 P007 절을 참고하세요.
기존 `1. Naive RAG/`와 LangChain 비교 화면의 데이터·동작은 유지됩니다.

## 먼저 볼 파일

- `data/source-v3/output/pdf/`: 생일 특별휴가, 연차, 재택근무, 복지, 교육휴가, 출장 PDF 6개
- `data/source-v3/authoring/`: 편집 원문 Markdown 6개
- `data/source-v3/extracted/canonical/`: PDF 리더로 읽고 NFC/LF만 정규화한 텍스트
- `data/source-v3/extracted/manifest.json`: 페이지 범위·텍스트/PDF hash·parser 버전
- `data/source-v3/section-map.json`: 작성한 19개 조항의 제목/본문 위치와 길이. 자동 제목 탐지 결과나 청크가 아닙니다.
- `data/source-v3/policy-map.json`: 기존 정책 31문장과 source-v2 전체 비제목 51블록의 대조, 새 위치·페이지·정확 인용
- `data/source-v3/handoff-manifest.json`: P007 준비 검토에 넘길 고정 파일 목록과 hash, 문서 길이·제약
- `data/source-v3/authoring-notes.md`: 수집에서 제외한 원래 학습 해설·안내·반복 풀이

PDF 한 페이지씩 총 6페이지입니다. 분량을 늘리려고 정책·예시·페이지 나눔을 추가하지 않았습니다.
시행일은 원자료에 없어 `null`이며 PDF에는 “정보 없음”으로 표시합니다.
가상 안내는 문서 앞에 한 번만 있고, 실제 페이지 번호·문서 식별자는 추출 텍스트에도 남습니다.

## 독립 실행

Python 3.12와 `ingestion-requirements.lock`의 pypdf 6.21.2만 있으면 PDF 수집·추출·검증을 실행할 수 있습니다.
부모 단계의 Python 모듈이나 실행 환경을 가져오지 않습니다. 다음 명령은 이 폴더에서 실행합니다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r ingestion-requirements.lock
.venv/bin/python scripts/validate_source.py --source-root data/source-v3
.venv/bin/python -m unittest discover -s tests -v
```

검증에 사용한 macOS 환경에서는 외부 Python 기반의 새 임시 venv에 기존 캐시 wheel을 오프라인 설치했습니다.
모델·전체 RAG 가상환경·색인을 복사하지 않았습니다. Python 패키지 설치와 별개로 모델 다운로드는 없습니다.

재수집/재추출은 항상 새로운 출력 경로를 사용합니다. 아래 `runs/`만 먼저 만들고, 하위 이름이
이미 있으면 새로운 이름을 정합니다. 기존 성공 결과를 덮어쓰지 않습니다.

```sh
mkdir -p runs
.venv/bin/python scripts/snapshot_drive_fixture.py --catalog data/source-v3/drive-fixture-catalog.json --output-dir runs/snapshot-01
.venv/bin/python scripts/ingest_documents.py --manifest runs/snapshot-01/manifest.json --output-dir runs/extracted-01
```

원본 PDF만 catalog에 등록됩니다. Markdown·학습 노트·정답/정책 대응 자료는 수집되지 않습니다.
Drive는 fixture ID와 합성 시각·null URL을 사용하는 로컬 복사이며 실제 Drive에 연결하지 않습니다.
canonical과 page map의 내용/hash 및 ingestion run ID는 반복 추출 시 일치합니다.
`elapsed_ms` 같은 실행 관측값까지 동일하다는 의미는 아닙니다.

## PDF 다시 작성

작성만 ReportLab 4.4.9와 `authoring-lock.json`의 글꼴을 추가로 사용합니다.
AppleGothic 13.0d1e3의 SHA256을 고정했고 폰트 파일은 배포하지 않습니다.
이 macOS 글꼴에는 OS/2 권한 필드가 없으므로 해당 필드로 재배포 권한을 단정하지 않습니다.
다른 컴퓨터에서 다시 작성하려면 적법하게 사용할 수 있는 동일 글꼴이 필요합니다.
배포된 PDF의 열람·추출에는 로컬 글꼴이나 ReportLab이 필요하지 않습니다.

```sh
python3 -m pip install reportlab==4.4.9
python3 scripts/create_source_pdfs.py --font /System/Library/Fonts/Supplemental/AppleGothic.ttf --output-dir runs/pdf-rebuild-01
```

전체 6문서가 성공해야 새 출력 디렉터리가 공개됩니다. 입력 문서·의존성 불일치, 출력 경로 재사용,
PDF 손상/암호화/누락, 캐시 hash 불일치, 페이지 map/인용 불일치를 오류로 구분합니다.
빈 페이지·이미지만 있는 페이지는 성공 corpus 대신 검토 대상으로 표시합니다. OCR은 수행하지 않습니다.

## 학습할 포인트와 다음 단계

1. PDF를 읽고 중요한 조건을 예상한 뒤 canonical에서 같은 내용을 찾습니다. 줄바꿈 때문에 문자열이 달라져도 정책 숫자·부정·예외는 남아야 합니다.
2. `section-map.json`의 위치는 Unicode 문자 위치입니다. PDF 좌표나 토큰 수가 아닙니다.
3. `policy-map.json`에서 “연 1일”, “수습 제외”, “긴급 시 당일 신청” 같은 짧은 조건이 보존되었는지 봅니다. 15개 기존 fact만으로 전체 정책 보존을 판단하지 않습니다.
4. P007은 이 고정 원문을 바탕으로 다섯 청킹 방식과 검색을 비교할 예정입니다. 원문 길이가 192~469자로 짧아 800자 설정은 차이가 없을 수 있습니다. 실제 길이를 근거로 plan에서 그리드·예산을 확정합니다.

`legacy-reference-map.json`은 기존 15fact/14질문의 의미를 새 원문 위치로 다시 찾은 **후속 참고 자료**입니다.
이미 관찰한 질문은 tuning이며 holdout이 아닙니다. 정책 대응표는 Codex의 원문 보존 대조이고,
사람 승인 Ground Truth·완성된 검색 qrels·답변 평가 점수가 아닙니다.
P007의 질문/정답·holdout, P013의 사람 승인 Reference Claims는 별도 준비가 필요합니다.

기존 다중 페이지 경계 fixture는 이전 단계에 보존했습니다. 새 원문은 복잡한 표·다단·OCR을 다루지 않으며,
이 작은 가상 자료의 실험 결과를 실제 회사 문서 전체로 일반화할 수 없습니다.

## 출처 및 고정 경계

`stage-manifest.json`에 복사한 파일의 전체 commit·원래 경로·hash·선별 이유가 있습니다.
`scripts/prepare_handoff.py`는 검토된 inventory와 명시적으로 전달한 이전 자료를 이용해 위치 대응 자료를
새 디렉터리에 재생성합니다. 기존 원문 경로를 자동으로 읽지 않습니다. 일반 열람·수집·추출·검증에는
이전 자료가 필요 없습니다. PDF/정규화 결과를 나중에 바꾸면 새 corpus 버전으로 분리해야 합니다.
