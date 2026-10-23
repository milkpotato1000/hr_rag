# 새 가상 원문 v2: Drive fixture → PDF/Markdown → 청크

이 원문들은 2026-10-23에 새로 작성했다. 과거 청크를 만들 때 사용했던 원본을 복구한 것이 아니다. 기존 15개 수작성 청크의 규정 의미를 유지하고 학습용 설명을 추가한 가상 자료이며 실제 회사 정책이 아니다.

업무 시나리오에서는 HR 담당자가 Google Drive 지정 폴더에 문서를 올린다. 이번 구현은 `source_provider=google_drive`, **`source_mode=fixture`**인 로컬 모사다. 실제 Drive 계정·폴더에 연결하거나 파일을 다운로드/업로드하지 않았다. `snapshot/cache/`는 다운로드 사본의 역할을 모사한다. 공개 저장소에는 이 가상 자료만 들어 있다.

## 원문을 보는 위치

| 주제 | 새로 작성한 편집 원문 | 모의 Drive의 대표 입력 |
| --- | --- | --- |
| 생일 특별휴가 | authoring/birthday.md | output/pdf/birthday.pdf (2페이지) |
| 연차 | authoring/annual.md | output/pdf/annual.pdf (2페이지) |
| 재택근무 | authoring/remote.md | 같은 Markdown |
| 복지 | authoring/welfare.md | 같은 Markdown |
| 교육 휴가 | authoring/training.md | 같은 Markdown |
| 출장 | authoring/travel.md | 같은 Markdown |

`drive-fixture-catalog.json`이 명시한 여섯 파일만 수집한다. 앞의 두 문서는 PDF를 선택하므로 대응 Markdown을 같은 corpus에 중복 수록하지 않는다. 임의 폴더 재귀 수집은 없다. PDF의 `<!-- pagebreak -->`는 작성용 구분자이며 PDF 본문에는 출력하지 않는다. PDF 생성 환경은 `pdf-authoring.json`에 기록했고, 한국어 글꼴 파일은 저장소에 복사하지 않았다.

## 산출물 경계

| 경로 | 의미 |
| --- | --- |
| snapshot/manifest.json | 모의 수집 목록·원격 메타데이터·대표 입력·바이트 해시 |
| snapshot/cache/ | 대표 입력 6개의 바이트 동일 사본 |
| extracted/pages/*.raw.txt | parser가 추출한 페이지별 원문 텍스트 |
| extracted/pages/*.txt | NFC/LF 정규화한 페이지 텍스트 |
| extracted/canonical/*.txt | 페이지를 `\n\n`으로 결합한 문서 텍스트 |
| extracted/manifest.json | 완료 상태, 원문/추출 해시, parser/정규화 버전, 페이지 offset, 처리 시간 |
| fixed-400-80/chunks.jsonl | 현재 구현한 fixed 문자 청크 20개 |
| fixed-400-80/source-map.json | 청크 → 원문 문자 위치·페이지 → cache hash → snapshot/file ID |
| fixed-400-80/manifest.json | 설정·해시·실행 ID·길이/겹침 통계 |
| evaluation-spec.json | 생성 결과를 보기 전에 작성한 원문 fact/질문/의미 기준 |
| evaluation/source-evaluation.json | 15개 fact, 29개 필수 span, 기존 14개 질문의 원문 평가 근거 |

## ID와 버전의 의미

- `document_id`는 학습 corpus의 논리적 문서 ID, `version=2`는 새 가상 문서 세대다.
- `file_id`, `folder_id`, `snapshot_id`는 모두 `fixture:` 접두어다. 이름 변경은 같은 file_id, 새로운 업로드는 새 file_id로 모사한다.
- `name`은 표시 이름이다. 파일 정체성이나 바이트 동일성을 이름으로 판단하지 않는다.
- `source_version=fixture-revision-1`은 합성 원격 메타데이터이며 문서 version과 별개다. 확인 불가 상황은 null을 허용한다.
- `source_modified_time`은 `timestamps_synthetic=true`로 표시한 합성 값이다. `collected_time=null`, `source_url=null`이며 실제 다운로드 시각이나 존재하지 않는 Drive 링크를 만들지 않는다.
- `downloaded_content_sha256=sha256`은 **모사한 cache 파일의 실제 바이트 해시**다. 경로 별칭 `local_path=path`와 함께 검증한다. 내용 변경은 다른 해시와 snapshot ID로 표현한다.
- snapshot ID는 경로·파일 목록·합성 메타데이터·콘텐츠 해시의 결정적 fingerprint다. 파일 이름만 바뀌어도 snapshot ID는 바뀔 수 있다. 청크 ID는 문서/콘텐츠/청킹 설정과 위치에 기반하므로 표시 이름 변경을 콘텐츠 변경과 혼동하지 않는다.
- snapshot에서 파일이 빠졌다는 사실만으로 실제 삭제를 단정하지 않는다. 실제 동기화·폴더 이동·삭제·권한 취소·활성 색인 전환은 구현하지 않았다.

후속 실제 Drive 어댑터는 지정 폴더만 읽고 실제 ID/링크/수정 시각과 다운로드 해시를 채워야 한다. Google Docs는 별도 export 형식/버전 계약이 필요하다. 현재 어댑터는 live 모드를 명시적으로 거부한다.

## 추출과 청킹 규칙

추출은 파일을 수정하지 않는다. pypdf 6.21.2가 PDF 페이지를 별도 프로세스에서 읽고, Markdown/TXT는 UTF-8로 읽는다. Unicode NFC와 CRLF/CR→LF만 정규화한다. 문장 재작성·요약·줄바꿈 합치기·머리말/바닥글 제거는 하지 않는다. 그래서 PDF 줄바꿈, 바닥글과 페이지 번호도 canonical text에 남는다.

offset은 canonical text의 **Unicode code point 기준 `[start,end)`**다. PDF 바이트 위치나 토큰 위치가 아니다. 페이지 사이 두 LF는 canonical text에는 속하지만 어느 PDF 페이지에도 속하지 않는다. source map의 페이지 범위는 실제 페이지 텍스트와 겹치는 부분만 기록한다.

청킹은 문서별 `start=0`, `end=min(start+400,length)`, 다음 start는 `start+320`이다. 마지막 끝에 도달하면 종료한다. 문서끼리 합치지 않고 제목을 본문에 추가하지 않는다. 공백뿐인 범위는 사유를 기록한 뒤 건너뛴다. 모든 청크 text는 canonical text의 정확한 slice다. **현재까지 fixed 문자 청킹만 구현했다. 400/80은 임시 비교 시작값이며 최적값·토큰 수·모델 사양이 아니다.**

기본 산출물: 6문서, PDF 4페이지 + Markdown 가상 페이지 4개, 5,669 canonical 문자, 20청크, 길이 85~400자, 평균 339.45자. 겹친 문자 비율은 `(청크 길이 합 - 문서별 범위 합집합 길이) / 청크 길이 합 = 1120 / 6789 ≈ 16.50%`다. 설정의 80/400=20%와 전체 산출물 비율은 다르다. 서로 다른 문서의 첫 청크와 마지막 길이 차이가 있기 때문이다.

내용/ID/source map 해시와 실행 ID는 같은 입력·설정에서 재현된다. 경과 시간은 관측값이므로 manifest 전체 바이트는 매번 같지 않을 수 있다. 청킹 실행 ID에는 시간 포함 artifact hash를 넣지 않고, 실제 입력 manifest 파일 해시는 별도 provenance 필드로 보관한다.

## 실패와 한계

- 이미지가 있고 텍스트가 없는 PDF 페이지: `ocr_candidate`.
- 이미지도 텍스트도 없는 페이지: `blank_candidate`. 벡터로 그린 글자는 이 분류에서 놓칠 수 있다.
- 위 페이지가 하나라도 있으면 `review.json`만 게시하고 CLI exit 3. 완료 `manifest.json`은 없으며 청킹은 거부한다. 페이지를 조용히 누락하지 않는다.
- 암호화/손상/미지원 형식, 잘못된 UTF-8, 해시 불일치, 경로 탈출, 중복 ID, 잘못된 offset, timeout은 오류(exit 2)다.
- 초기 보호값은 파일당 20 MiB, PDF 100페이지, canonical 문서 100만 문자, PDF 별도 프로세스 timeout 30초다. 모든 PDF의 메모리/자원 사용을 보장하는 sandbox는 아니다.
- 출력은 새 디렉터리에만 같은 파일시스템의 원자적 no-replace rename으로 게시한다. macOS/Linux를 지원하며 기존 출력/색인을 덮어쓰지 않는다.
- OCR·복잡한 표·다단 독서 순서 복원은 구현하지 않았다. 이 단일 열 PDF 4페이지는 직접 렌더링과 텍스트를 대조했지만 일반 PDF의 정확성을 보장하지 않는다. [pypdf의 추출 한계](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)를 참고한다.

## 평가를 읽는 방법

fact마다 하나 이상의 필수 원문 span이 있다. 여러 청크가 합쳐져 하나의 사실을 담을 수 있다. 각 span의 quote는 줄바꿈을 포함한 canonical text의 정확한 부분 문자열이다. 기존 14개 질문의 문장과 답변 가능 여부는 유지했지만 기존 chunk ID 기반 qrels를 복사하지 않았다. 검색/생성 입력은 chunks만 받으며 이 평가 파일을 읽지 않는다.

현재 실제 400/80 산출물에서는 각 개별 fact를 완전히 포함하는 청크가 하나 이상 존재한다. 복수 청크로만 한 fact를 충족하는 상황은 독립 작은 fixture로 검증했다. 생일 휴가 종합 질문처럼 여러 fact를 묻는 질문은 여러 위치의 근거를 필요로 한다. 청킹 비교 검색 지표는 P007, 최종 답변 비교와 UI 전환은 P008에서 다룬다.
