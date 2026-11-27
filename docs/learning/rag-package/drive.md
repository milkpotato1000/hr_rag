# Google Drive 단일 문서 연결

Google Drive의 PDF/TXT/MD와 Google Docs의 PDF export를 일반 RAG snapshot에 연결하는 코드를 구현했습니다. **SDK 설치·가짜 인증/HTTP·합성 문서로 검증했으며 실제 Google 로그인이나 사용자 파일 수집은 하지 않았습니다.** P013 모델 실행은 계속 보류합니다.

[학습 시작점](README.md) · [일반 문서 RAG](document-rag.md) · [검증 기록](../../verification/p027/README.md)

## 지금 지원하는 입력

| 입력 | 지원 범위 |
| --- | --- |
| drive.google.com/file/d/ID/view 또는 /file/d/ID | 단일 일반 파일 |
| drive.google.com/open?id=ID | 단일 일반 파일 |
| docs.google.com/document/d/ID/edit 또는 /document/d/ID | Google Docs PDF export |
| PDF / text/plain / text/markdown | 서버 MIME를 기준으로 선택, text/plain 이름이 .md이면 Markdown |
| 공유받은 일반 파일 | 실제 로그인 계정에 다운로드 권한이 있는 경우. 이번 실계정 검증은 미수행 |

HTTPS만 받으며 사용자정보·포트·fragment·중복 ID/resourcekey를 거부합니다. resourcekey는 필요할 때만 고정 Google API 요청 헤더로 전달하며 결과와 로그에는 남기지 않습니다. 표시용 usp/tab query는 전달하지 않습니다. 폴더 순회·shortcut·shared drive·Sheets/Slides/Office/HTML·OCR·암호 PDF는 지원하지 않습니다. 이름을 .pdf로 바꿔 MIME 검사를 우회할 수 없습니다.

일반 blob은 20MiB, Google Docs export는 보수적으로 10,000,000 bytes까지입니다. exported PDF에는 P026의 페이지/문자/파싱 한도가 추가 적용됩니다. Google의 export 제한과 파일 종류는 [공식 다운로드 안내](https://developers.google.com/workspace/drive/api/guides/manage-downloads)를 참고하세요.

## 인증을 정하기 전에

이 connector는 본인의 OAuth access token 또는 Desktop OAuth client를 사용합니다. API key, Codex/Claude Code 구독이나 코딩 도구의 Drive connector 인증을 대신 사용할 수 없습니다.

scope는 `https://www.googleapis.com/auth/drive.readonly` 하나입니다. **선택한 파일 하나만 읽는 권한이 아니라 계정에서 접근 가능한 Drive 파일을 읽을 수 있는 restricted scope입니다.** 기존 문서 링크를 받기 위한 첫 구현이며 drive.file/Picker로 범위를 좁히는 방식은 후속입니다. [공식 scope 안내](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)에서 범위를 확인하세요.

Google Cloud에서 프로젝트와 Drive API, OAuth 동의 화면·테스트 사용자·Desktop client를 설정합니다. 조직 정책이나 앱 테스트 상태에 따라 사용할 수 있는 계정이 제한될 수 있습니다. 공개 배포 시에는 Google의 검증 요구를 별도로 확인해야 합니다. 이 저장소가 사용자의 앱 등록·승인을 대신 완료한 것은 아닙니다.

## 선택 OAuth SDK 설치

Python 3.10+가 필요합니다. token-env와 preview는 SDK 없이 동작합니다. OAuth helper는 [requirements-drive.lock](../../../rag_package/requirements-drive.lock)의 정확 SDK 및 해시를 사용합니다. 기존 모델 환경과 분리한 새 venv를 만드세요.

```sh
python3 -m venv .rag-runs/drive-sdk/.venv
.rag-runs/drive-sdk/.venv/bin/python -m pip install --require-hashes -r rag_package/requirements-drive.lock
```

이번 개발에서는 별도 P027 venv에 google-auth-oauthlib 1.5.0/google-auth 2.63.1과 전이 의존성을 설치·검증했습니다. 기존 venv와 lock은 바꾸지 않았습니다. PDF 시험은 기존 설치된 pypdf 6.21.2를 읽기 전용으로 재사용했습니다. 새 환경에서 PDF 수집도 하려면 [선택 PDF 의존성](../../../rag_package/requirements-pdf.lock)을 해당 새 환경에 설치해야 합니다. 이를 다른 OS의 설치 성공으로 일반화하지 않습니다.

## 먼저 preview

`hr_rag_dev/` 루트에서 다음 두 명령은 secret 값·SDK·OAuth·HTTP·모델을 사용하지 않습니다. 샘플 ID는 실제 파일이 아닙니다.

```sh
python3 -m rag_package drive-preview --config examples/drive/token-env.json
python3 -m rag_package drive-pull --config examples/drive/token-env.json --out .rag-runs/drive-preview
```

execute 없는 pull은 다운로드하거나 출력 폴더를 만들지 않습니다. 실제 권한·MIME·버전을 확인했다는 표시도 하지 않습니다. [token-env 예시](../../../examples/drive/token-env.json)와 [oauth-file 예시](../../../examples/drive/oauth-file.json)를 개인 설정 파일로 복사한 뒤 URL과 인증 참조를 바꾸세요. 설정에는 token 값이 아니라 환경 변수 이름 또는 저장소 밖의 credential 경로만 넣습니다. 추가 필드·직접 token·중복 JSON 키를 거부합니다.

## 실제 사용자 실행 절차

아래 login/pull의 execute는 실제 브라우저·Drive 접근을 시작하는 **사용자 실행 예시**이며 이번 개발에서 실행하지 않았습니다. 실문서 수집과 LLM 전송은 별개입니다.

1. 저장소/워크스페이스 밖에 전용 디렉터리를 준비하고 권한을 0700으로 설정합니다. Desktop client JSON과 credential 파일은 0600, symlink 없이 사용합니다. client JSON도 해당 보호 디렉터리에 보관합니다.
2. OAuth helper를 사용할 때는 SDK가 설치된 Python으로 다음 문법을 사용합니다. execute를 빼면 파일 내용을 읽지 않고 안내만 표시합니다.

```text
python3 -m rag_package drive-login --client-secret-file /개인전용디렉터리/client.json --credentials-file /개인전용디렉터리/credentials.json --execute
```

브라우저에서 직접 로그인·동의합니다. SDK의 state/PKCE를 사용하고 callback은 127.0.0.1·임의 포트·300초 대기입니다. 기존 credential 파일은 덮어쓰지 않으므로 별도로 보관하거나 새 경로를 지정하세요. 공식 auth/token endpoint만 허용하고 SDK HTTP도 TLS 검증을 유지하며 환경 proxy·redirect를 사용하지 않습니다. 인증 URL/refresh token을 보고서에 저장하지 않습니다.

3. oauth_file 설정을 선택하거나, 외부에서 발급한 본인 access token을 설정에 지정한 환경 변수에 넣습니다. token 값을 문서·Git·CLI 인수에 적지 마세요. 만료 token으로 401을 받으면 자동 로그인/재시도하지 않습니다. oauth_file은 execute 전에 필요할 때 최대 한 번 refresh하고 보호 파일을 원자적으로 갱신합니다.
4. 개인 설정으로 preview를 확인한 뒤 새로운 출력 경로로 명시 pull합니다.

```text
python3 -m rag_package drive-pull --config /개인설정/drive.json --out .rag-runs/drive-001 --execute
```

5. 수집 결과가 ready라면 `snapshot/`을 P026에 전달합니다. 아래 build/ask는 기본 preview이므로 모델을 호출하지 않습니다.

```sh
python3 -m rag_package build --snapshot .rag-runs/drive-001/snapshot --config examples/rag/fixed.json --out .rag-runs/drive-build-001
python3 -m rag_package ask --run .rag-runs/drive-build-001 --config examples/rag/fixed.json --question '이 문서의 주요 조건은?' --out .rag-runs/drive-answer-preview-001
```

실제 답변 생성은 별도로 전송 문서·provider/model·키·호출/비용 상한·중지 조건을 정한 후 ask의 `--execute`를 사용합니다. Drive 로그인만으로 LLM 호출 권한이나 P013 재개 권한이 생기지 않습니다.

## 무엇을 검증하고 저장하나

metadata-before → download/export → metadata-after 순서로 Drive GET 요청 최대 3회입니다. metadata는 256KiB, 각 socket 대기는 30초, 다운로드 구간의 전체 deadline은 60초입니다. redirect·proxy·자동 retry는 없습니다. size와 제공된 SHA256/MD5를 검증하고 없으면 unavailable로 남깁니다. Google Docs의 hash는 이번 PDF 변환 bytes를 가리키며 원본 Docs 고유 content hash가 아닙니다.

전후 version/modifiedTime/MIME/size/checksum/권한·trashed 등을 비교하고 바뀌면 source_changed로 저장하지 않습니다. **metadata 전후 비교는 낙관적 일관성 검사이며 원자적 revision 다운로드 보장은 아닙니다.** 같은 Docs version도 export 엔진 변화로 bytes가 달라질 수 있습니다.

출력에는 `receipt.json`과 `snapshot/`이 있습니다. receipt에는 허용 metadata, bytes/hash, 요청 단계/횟수, snapshot fingerprint와 검증 범위를 기록합니다. snapshot의 origin에는 file_id/version/modified_time/MIME/export 형식/hash/실행 종류가 들어가며 identity에 포함됩니다. index 사본과 답변의 source_origins에도 이어집니다. 실제 원격 자료는 synthetic=false, 가짜 시험은 test_fixture로 구분합니다.

token/resourcekey/인증 헤더/전체 입력 URL/credential 경로는 저장하지 않습니다. file_id와 문서 이름·원문 자체도 개인 metadata이므로 실제 결과는 공개 Git에 넣지 마세요. `.rag-runs/`는 Git 제외이며 다른 출력 경로도 직접 관리해야 합니다.

## 실패와 재수집

| 오류 | 해석과 조치 |
| --- | --- |
| 401 auth_error | token 만료/인증 실패. 자동 refresh/retry 없이 인증 상태 확인 |
| 403 access_denied | 접근 거부. 본인 권한·앱/조직 정책 확인 |
| 404 not_found_or_inaccessible | 없거나 접근 불가. 삭제와 권한 은폐를 추측해 구분하지 않음 |
| 429 rate_limited / 5xx upstream_error | 자동 재요청 없음. 오류 기록과 서비스 상태 확인 |
| source_changed / checksum·size 오류 | 전후 개정 또는 전송 불일치. 기존 결과 보존 후 새 경로로 명시 재수집 |
| needs_review | PDF 빈/스캔/암호·파싱 제한 등. ready index로 사용하지 말고 reason 확인 |
| 출력 저장·출판 실패 | 요청 단계/횟수·dispatch 여부 보존. 자동 재수집 없음 |
| OAuth 경로/권한/SDK 오류 | 저장소 밖 절대경로·0700/0600·symlink·정확 SDK 버전 확인 |

문서가 바뀌면 새 pull → 새 snapshot → 새 build를 수행합니다. 이전 index를 덮어쓰지 않습니다. 현재는 사용자 명시 재수집이며 자동 동기화·변경 감시·삭제 전파를 구현한 것은 아닙니다.
