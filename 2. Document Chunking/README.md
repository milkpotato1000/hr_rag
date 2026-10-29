# Document Chunking - 원문 준비

P015에서 준비한 가상 HR 규정 원문입니다. 현재 범위는 PDF 작성, 로컬 수집 fixture,
텍스트 추출 및 정책 보존 대조까지입니다. 청킹·검색·모델 호출·웹 화면은 아직 구현하지 않았습니다.
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
