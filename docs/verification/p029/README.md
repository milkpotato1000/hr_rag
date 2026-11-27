# P029 검증 기록

정확 plan `e0d44e097c58da1c2944c8c16ce15a06c95b90b9`, dev adoption `79958fc`. 설치된 실제 문서 코어를 사용하는 UI를 구현했다. **C1~C3 검증 PASS, C4는 실제 브라우저 업로드 관찰이 차단되어 미완료다.** 전체 P029/패키지 goal 완료가 아니다.

## 실행 근거

- [전체 61개 테스트](tests-ui-refined.log): P025~P028 51개와 UI 10개. 실제 core·HTTP 경계, Unicode, 후보/제외 원문 연결, 세 chunker, compare, clone/export, secret 비노출, duplicate/busy/restart/쓰기 실패를 검사했다. [초기 6개](ui-initial.log), [첫 전체 60개](tests-all-first.log)도 보존했다.
- 실행 명령: `.rag-runs/p027-sdk/.venv/bin/python -m unittest discover -s tests/rag_package -v`. 테스트 network는 소유 loopback 또는 injected backend만 허용한다.
- [최종 설치](installation.json), [빌드 명령](build-install-commands.json): 기존 P028 격리 build venv에서 allowlist payload→sdist→wheel, 새 source-free venv에 설치, build source 제거 후 실행했다. [빌드 스크립트](build_install.py). 이전 wheel/명령은 `installation-first.json`, `build-install-commands-first.json`으로 보존한다.
- [설치 후 회귀](installed-regression.json): source 없는 cwd/PYTHONPATH unset에서 init/doctor/규칙3종/preview/compare9행/PDF/SDK/placeholder/Git credential 경계. [로그](installed-regression.log). P028의 커밋된 `installed_probe.py`를 새 환경에 복사해 실행했다.
- [설치 CLI](installed-cli.json): 실제 `rag-lab serve` entrypoint·bootstrap·샘플2개·기본 실행 flags false·종료0. 실제 provider/Drive 호출0.
- [브라우저 관찰](browser-observations.json), [데스크톱](desktop-answer.jpg), [좁은 화면](narrow-answer.jpg). 가상 답변은 시험 데이터이며 실모델 답변 품질 증거가 아니다.
- [첫 서버 종료](browser-first-server.json), [최종 서버 종료](browser-final-server.json). [fixture 코드](browser_fixture.py)는 배포물에 포함되지 않는다. 실제 outbound connect/DNS를 금지한 설치 wheel에서 fake model/Drive만 주입했다.
- [보존/출처/링크 검사](checks.json), [시작 hash](preservation-before.json). 기존 단계·GT·P013 실행/승인/grant 및 기존 locks 보존. 제품 소스는 새 UI이며 이전 단계 디자인/알고리즘을 복사하지 않고 기존 package core를 호출했다. UI용 Drive memory adapter는 기존 path API를 보존한다. 새 runtime 의존성/CDN/telemetry 없음.

## 실패·수정과 미완료 항목

첫 브라우저 검사에서 후보 rank가 비어 보였고, 390px 화면의 긴 usage JSON으로 document width가 469px였다. 후보 순서로 rank를 표시하고 긴 문자열의 줄바꿈을 적용한 뒤 새 wheel을 만들었다. 최종 실제 화면에서 390/390px, 1280/1280px와 1~4위 표시를 확인했다. 후보/제외 본문과 원문 이동은 검증한 build chunks에 연결했으며 non-BMP fixture의 codepoint 길이도 검사했다.

파일 선택은 IAB filechooser 작업이 617초 뒤 continuation 오류로 끝났다. 이후 문서화된 native fallback `cua.getApp('Codex')`가 **Computer Use is not allowed to use the app 'com.openai.codex' for safety reasons**로 거부됐다. 다른 앱/도구/URL로 이 차단을 우회하지 않았다. 업로드 HTTP 시험 PASS를 실제 브라우저 업로드 성공으로 표시하지 않는다. C4와 STATE는 BLOCKED로 남긴다. 남은 것은 정책이 허용하는 브라우저 파일 선택/업로드→snapshot 실관찰이다. 사용자에게 기존 run004 확인을 반복 요청하지 않았다.

실제 브라우저에서 샘플 snapshot/build/preview/정확 quote/fake answer/원문 locate/두 설정 비교/모델 form/Drive form/키보드/좁은 화면을 관찰했다. 실제 모델/API/Drive/OAuth/개인 key 호출0, 모델 다운로드·서버 시작0. 소유 UI 검증 서버만 시작·종료했다. P013 BLOCKED와 미소비 grant 유지. 시험 플랫폼은 같은 Mac/Python3.12이며 다른 OS·두 코딩 도구 제품 UI·실모델 품질을 검증하지 않았다.
