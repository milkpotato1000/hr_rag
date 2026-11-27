# P027 Drive 연결 준비 조사 — 2026-11-27

P027은 아직 DRAFT다. 이 문서는 P026 구현과 독립적으로 확인한 공식 근거/후속 계약 결정을 보존하며 실행 허가나 계정 접근 승인이 아니다.

## 실제 문서 링크와 다운로드

[공식 다운로드/내보내기 안내](https://developers.google.com/workspace/drive/api/guides/manage-downloads): PDF 등 blob은 files.get alt=media, Google Workspace 문서는 files.export로 처리한다. capabilities.canDownload를 먼저 확인한다. Google 문서 export에는 별도 크기/형식 제한이 있어 PDF 다운로드와 동일한 path로 가정하지 않는다. 본 프로젝트의 기존 Drive fixture는 API 호출이 아니다.

[Resource key 안내](https://developers.google.com/workspace/drive/api/guides/resource-keys): 공유 링크의 resourcekey가 필요한 파일이 있고 요청의 X-Goog-Drive-Resource-Keys 헤더로 전달한다. resource key는 접근권한을 우회하는 수단이 아니다. 문서 ID와 resourcekey만 분석하고 arbitrary URL/redirect에 credentials를 보내지 않는 API 경계가 필요하다.

[files.get](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/get): metadata와 content를 분리해 필요한 fields만 요청한다. metadata 읽기→content 수집→metadata 재확인의 낙관적 버전 확인을 검토한다. 이 절차를 서버 원자적 snapshot 보장이라고 부르지 않는다. 변경/삭제/권한 손실이면 이전 snapshot/index를 자동 최신으로 표시하지 않는다.

## 배포 패키지의 사용자 인증

[Python quickstart](https://developers.google.com/workspace/drive/api/quickstart/python)는 사용자 Google 계정/Cloud 프로젝트와 별도의 OAuth client 설정을 전제로 한다. ChatGPT/Codex의 연결 계정이 배포 CLI에 자동 이전되는 구조가 아니다. 패키지 문서에 최초 설정과 실제 승인 주체를 명시해야 한다.

[Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)를 기준으로 최소 범위를 선택한다. 임의 기존 파일 링크에 대한 readonly 요구와 drive.file의 앱 선택 파일 범위는 다르므로 더 작은 이름의 scope만 고른다고 목적을 충족하는 것은 아니다. 범위 밖 파일을 찾으려 권한을 자동 넓히지 않는다. 앱 공개 배포와 개인 개발 OAuth 설정의 요구도 구분한다.

인증 구현은 [InstalledAppFlow](https://googleapis.dev/python/google-auth-oauthlib/latest/reference/google_auth_oauthlib.flow.html) 및 [google.oauth2.credentials](https://googleapis.dev/python/google-auth/latest/reference/google.oauth2.credentials.html)를 활용하는 방향을 검토한다. 실제 SDK version/dependency lock은 READY 시 확정한다. credential은 사용자 지정 저장소 밖 위치, access/refresh token과 OAuth client secret은 출력/로그/공개 저장소에 넣지 않는다. refresh token이 있는 인증과 일회 access-token 주입을 구분한다. token 만료·취소와 사용자 재로그인은 자동 접근권한 변경으로 해결하지 않는다.

## 확정해야 할 경계

P026 snapshot schema 완료를 관찰한 뒤 단일 PDF/TXT/MD 링크와 Google Docs export 지원, folder/shortcut/shared-drive 포함 여부, OAuth helper와 token 입력, version 충돌/다운로드 크기/timeout·총 요청 한도, P026 연결 방식을 READY 계약으로 확정한다. URL preview는 인증/다운로드 없이 분석만 하고 실제 connect는 명시 명령에서 수행한다.

새 connector는 실제 API 코드를 구현하되 개발 검증은 synthetic metadata/bytes와 fake transport부터 진행할 수 있다. 실제 Google 계정/문서 E2E는 지정 입력과 사람의 로그인으로 별도 검증한다. fixture 통과를 Drive live 연결 완료라고 보고하지 않는다. 특정 개인 문서가 아직 없어도 코드/fixture/설치 안내 준비는 진행할 수 있다.
