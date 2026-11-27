# P027 — Google Drive 단일 문서 connector 계약 v1

## 목적과 경계

P026 일반 snapshot에 실제 Google Drive 다운로드 경로를 연결한다. 구현은 실제 REST/OAuth 호출 경로까지 제공하되 이번 개발 검증은 합성 문서·가짜 HTTP/인증 backend와 소유 loopback 서버만 사용한다. 사용자 Drive, 로그인, 실제 credential, LLM/API/모델 다운로드는 실행하지 않는다. P013 보류와 P010/P020 기존 선행을 유지한다.

지원 Python 3.10+. `rag_package/connectors/`, `rag_package/drive_auth.py`, 기존 일반 CLI/snapshot의 호환 확장, `examples/drive/`, `tests/rag_package/`, `docs/learning/rag-package/drive.md`, `docs/verification/p027/`가 구현 경로다. 기존 HR 단계·평가·GT·locks·실행 기록은 수정하지 않는다. 새 저장소나 main 승격은 범위 밖이다.

## 링크와 형식

첫 지원은 한 번에 단일 파일이다. HTTPS `drive.google.com/file/d/{id}/view`, `drive.google.com/open?id={id}`, `docs.google.com/document/d/{id}/edit` 형식을 받는다. 마지막 view/edit suffix 생략도 허용한다. URL 사용자정보·포트·fragment·중복 id/resourcekey·다른 호스트·폴더·다른 Google 앱 링크는 거부한다. id/resourcekey는 ASCII 영숫자, `_`, `-`만 허용하고 길이는 1..200으로 제한한다. `usp`, `tab` 같은 표시용 query는 네트워크 목적지에 전달하지 않는다. 단 하나의 `resourcekey`만 optional로 읽으며 출력/로그에서 제거한다. URL을 따라가는 crawler가 아니라 id를 추출해 고정 Drive API에 요청한다.

서버 metadata MIME를 기준으로 PDF(application/pdf), UTF-8 text/plain(.md 이름은 Markdown으로 분류), text/markdown, Google Docs(application/vnd.google-apps.document)의 PDF export만 지원한다. 일반 blob 최대 20MiB, Google Docs export는 서비스 10MB 제한을 감안해 클라이언트에서 보수적으로 10,000,000 bytes까지 허용한다. Office/Sheets/Slides/HTML/폴더/shortcut/shared-drive(driveId 존재)/암호화 문서는 명시 unsupported다. 이름 확장자로 MIME를 우회하지 않는다. shared-with-me 일반 파일은 실제 권한이 있으면 가능하다. 다중 파일/폴더 순회·변경 감시·삭제 전파·다른 웹하드·OCR는 후속이다.

## CLI와 입력

- `python -m rag_package drive-preview --config FILE`: strict JSON/링크/옵션 검증과 필요한 권한·지원 형식 안내. 환경 secret 읽기·SDK import·OAuth·HTTP·다운로드·모델 호출 0. 실제 파일 접근 가능/형식/버전을 확인했다고 표시하지 않는다.
- `python -m rag_package drive-pull --config FILE --out NEWDIR [--execute]`: 기본은 위 preview. execute일 때만 인증과 다운로드→snapshot. 새 output은 P026 staging/no-clobber/atomic publish를 사용한다.
- `python -m rag_package drive-login --client-secret-file PATH --credentials-file PATH --execute`: 명시 실행 시만 브라우저 로그인. execute 없으면 경로/권한 안내만, 파일 내용을 읽지 않는다. login은 문서 다운로드나 모델 호출을 하지 않는다.

config v1의 정확 필드: `schema_version:1`, `connector:"google_drive"`, `url`, `auth`. auth는 `{mode:"access_token_env",env:"ENV_NAME"}` 또는 `{mode:"oauth_file",credentials_file:"ABSOLUTE_PATH"}` 중 하나다. 추가 필드/직접 토큰/빈값/중복 JSON 키/nonfinite는 거부한다. env 이름만 설정에 저장한다. 상대 config path 해석은 P025 방식과 같되 credential 파일은 절대경로이며 저장소 밖에 있어야 한다. 샘플은 가짜 id/키 이름만 포함한다. 실행 산출물은 `.rag-runs/` 또는 저장소 밖을 사용하며 실제 문서와 URL/resource key를 공개 Git에 넣지 않는다.

## 인증

access_token_env는 사용자가 외부에서 발급한 본인 OAuth access token을 execute 순간에만 읽는다. API key/코딩 도구 구독/코딩 도구 connector 인증을 대체재로 설명하지 않는다. 빈 token·CR/LF는 네트워크 전에 거부, 만료 시 자동 로그인/재요청하지 않는다.

OAuth는 공식 `google-auth-oauthlib==1.5.0`, `google-auth==2.63.1` 후보를 optional dependency로 고정한다. dev는 격리한 P027 venv에서 공식 PyPI package의 의존성 해석/설치·import 검사만 수행할 수 있다. 모델 다운로드는 아니다. 실제 배포 dependency 버전/hash를 lock과 증거에 기록하고 기존 venv/lock을 수정하지 않는다. 호환되지 않으면 검증 실패를 보고하며 다른 버전으로 조용히 바꾸지 않는다. core import/preview/token-env 사용에는 SDK가 없어도 된다. fake backend 테스트만으로 SDK 설치 검증을 대체하지 않는다.

login은 사용자가 만든 Desktop OAuth client JSON을 이용한다. scope는 `https://www.googleapis.com/auth/drive.readonly` 하나. 이는 선택 파일 하나에만 제한된 권한이 아니라 사용자에게 접근 가능한 Drive 파일을 읽을 수 있는 restricted scope임을 안내한다. 범용 기존 링크 접근을 위해 선택했으며 drive.file/Picker 범위 축소는 후속이다. 개인 테스트 앱 설정/테스트 사용자/조직 정책과 공개 배포 시 Google 검증 필요성을 가이드에 명시한다.

InstalledAppFlow의 state/PKCE 처리를 사용하고 callback은 127.0.0.1·임의 포트·대기 300초로 제한한다. 브라우저는 사용자가 실행한 login에서만 연다. client JSON은 installed 타입과 공식 auth/token endpoint를 검증한다. refresh token을 stdout/보고서/exception 원문에 출력하지 않는다. SDK HTTP session은 TLS 검증 유지, 환경 proxy를 자동 사용하지 않으며 허용 token endpoint 외로 credential을 전송하지 않는다. token URI를 임의 credential JSON에서 그대로 신뢰하지 않는다. OAuth browser authorization URL 출력이 필요하면 사용자 로그인 터미널만 허용하며 durable artifact에 저장하지 않는다.

credential 파일은 저장소 밖의 사용자가 지정한 전용 디렉터리(권한 0700), 파일 0600, symlink 거부, atomic 저장한다. 기존 파일은 login에서 덮어쓰지 않는다. 사용자가 기존 파일을 따로 보관하거나 새 경로를 지정한다. oauth_file execute는 만료 여부 확인 후 필요할 때 공식 SDK로 최대 한 번 refresh하고 같은 보호 경로에 atomic 갱신한다. refresh 실패는 auth_error; API 401을 받아 자동 refresh/retry하는 숨은 재요청은 하지 않는다. scope 누락/다른 token URI/불안전 파일 권한/SDK 미설치는 명시 실패한다. 테스트는 외부 network 없이 이 분기를 검증한다.

## REST 수집과 일관성

production HTTP 대상은 `https://www.googleapis.com/drive/v3/files/{validated_id}`와 같은 id의 `/export`뿐이다. GET only, 정상 TLS, no proxy/no redirects/no auto retry. Bearer/resource key는 이 API에만 전송한다. resource key header는 `X-Goog-Drive-Resource-Keys: id/key`. test transport/loopback은 dependency injection으로만 제공하며 사용자 config로 임의 endpoint를 허용하지 않는다.

파일마다 metadata-before → download/export → metadata-after 3회 이내 Drive 요청. auth refresh는 별도 1회 이내다. metadata는 최대 256KiB, 각 요청 socket timeout 30초와 다운로드 전체 60초 한도, bounded streaming, Content-Length 초과/일치 오류·빈 body·부분 응답·206·redirect·비정상 status를 실패로 처리한다. 요청 건수/단계/dispatch 여부를 기록하며 timeout/출력 실패 후 자동 재실행하지 않는다.

metadata는 id/name/mimeType/version/modifiedTime/trashed/capabilities.canDownload/size/md5Checksum/sha256Checksum/driveId만 요청·필요 필드 strict 검증한다. id 일치, version 숫자 문자열, modifiedTime, canDownload=true, trashed=false를 확인한 뒤 다운로드한다. metadata 크기 선검사와 실제 stream 크기 검사를 모두 한다. blob은 `alt=media`, Google Docs는 `export?mimeType=application/pdf`. blob의 size와 제공된 checksum을 검증한다(sha256 우선, md5가 있으면 함께 검증; 없으면 unavailable 기록). checksum 미제공을 임의 값으로 채우지 않는다.

after metadata에서 version/modifiedTime/MIME/size/checksum 및 다운로드 가능 여부·trashed 상태를 before와 비교한다. 달라지면 source_changed로 publish하지 않는다. metadata 전후 검사는 optimistic consistency이며 서버의 원자적 revision download 보장은 아니다. Google Docs export의 byte hash는 이번 변환 결과의 hash이며 원본 Docs의 고유 content hash로 주장하지 않는다. export 엔진 변화로 같은 문서 version의 bytes가 달라질 수 있음을 기록한다.

404는 not_found_or_inaccessible로 표시한다. 존재하지 않음/삭제/권한 은폐를 추측해서 구분하지 않는다. 401 auth_error, 403 access_denied, 429 rate_limited, 5xx upstream_error, 기타 response/parse/timeouts는 고정 오류 코드로 구분하고 raw response/토큰/URL query를 기록하지 않는다. 실패 산출물이 남더라도 성공 snapshot으로 소비되지 않아야 한다.

## Snapshot 연결과 재현성

output은 불변 `receipt.json` + `snapshot/` 구조다. P026 snapshot parser를 그대로 호출하고 needs_review면 상태와 이유를 전달한다. 문서 id는 Drive id의 SHA256 기반 안정 ID, title은 remote name을 표시 문자열로만 사용하고 파일 경로에는 넣지 않는다. 실제 원격 문서는 synthetic=false, test fixture는 execution_kind=test_fixture로 분명히 구분한다.

P026 snapshot 생성 함수에 optional 내부 origins mapping을 추가할 수 있다. 기존 sources JSON/로컬 snapshot contract는 그대로 유지한다. remote 문서 record의 optional `origin`은 provider, file_id, remote_version, modified_time, mime_type, export_mime(nullable), downloaded_sha256, consistency="metadata_before_after", execution_kind(live/test_fixture)를 포함한다. origin은 identity fingerprint에 포함하고 load_snapshot에서도 schema/hash와 original_sha256 일치를 검증한다. 이전 origin 없는 snapshot은 계속 읽힌다. receipt는 snapshot fingerprint, before/after의 허용 metadata, 다운로드 hash/byte수, 측정 시간, 요청 단계·건수, 실제 검증 범위를 기록한다. token/resourcekey/auth headers/전체 원래 URL/credential path는 포함하지 않는다. file_id와 title도 private metadata이므로 실제 receipt는 공개 Git에 넣지 않는다.

새 다운로드는 새 디렉터리로만 생성하며 이전 index를 덮어쓰지 않는다. P026 build에 `OUT/snapshot`을 전달하고 origin이 index copy/trace에 보존됨을 시험한다. 변경된 version 또는 bytes는 새 fingerprint가 되어 기존 index와 섞이지 않아야 한다. 이 단계의 '변경 반영'은 사용자가 재수집하고 rebuild하는 명시 절차이며 자동 sync라고 설명하지 않는다.

## 검증과 완료

성공 fixture: blob PDF/TXT/MD·Google Docs PDF export·resource key·OAuth cached/refresh·env token·snapshot→build→ask-preview 연결. 실패 fixture: 링크 혼동/credentials 주입/폴더·shortcut·shared drive/권한/404/만료/변경 경쟁/checksum/길이·빈body/timeout/redirect/모든 output 저장실패/중복 output/scan PDF needs_review. secret sentinel이 stdout·exception·artifact에 없는지 확인한다. preview의 secret/HTTP/SDK 호출0을 강제한다.

OAuth 실제 SDK import·호출 signature를 설치된 버전으로 검증하고 network/auth backend를 대체한다. production Drive transport도 소유 loopback 서버와 fake credential로 경계 동작을 시험한다. transport 대체 시 execution_kind는 항상 test_fixture다. private 실제 계정 시험을 수행하거나 성공했다고 표시하지 않는다. offline 성공과 live E2E 미실행을 README/결과에 분리한다.

P025/P026 regression과 기존 기준선 hash 보존을 검증한다. 가이드에는 Google Cloud 설정→login 또는 token env→preview→pull execute→snapshot→build→ask preview/명시 execute, 재수집, 실패 복구와 지원표를 제공한다. LLM execute 명령은 사용자 실행 예시이며 이번 dev가 수행할 작업이 아니다. 증거/체크/append-only 로그를 커밋하고 normal personal/dev push한다. main은 변경하지 않는다.

## 근거

2026-11-27 확인: [다운로드·export](https://developers.google.com/workspace/drive/api/guides/manage-downloads), [File metadata](https://developers.google.com/workspace/drive/api/reference/rest/v3/files), [resource key](https://developers.google.com/workspace/drive/api/guides/resource-keys), [OAuth 범위](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [InstalledAppFlow](https://googleapis.dev/python/google-auth-oauthlib/latest/reference/google_auth_oauthlib.flow.html). 버전 후보와 공개 SDK 근거는 [사전 조사](../reviews/P027-source-research.md)를 따른다. 요청/파일/시간 한도와 지원 축소는 이 프로젝트의 구현 선택이다.
