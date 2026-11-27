# P020 고정 후보 리랭킹 검증

정확 plan `f6800d0bd60b6345917533efd831fe2892dfb751`을 adoption `e2bd76e`에서 채택했다. P010 완료 `3d99353b5aef3b683b24d0f7fa06b8a757dc1f83`를 기준으로 후보 고정, none/두 CrossEncoder, 비교·모델 없는 보고서, 선택 문맥의 generation 연결, CLI/UI를 구현했다. **사전학습 가중치 다운로드·로드, 실제 LLM/API/Drive/OAuth/개인키 호출은 0회**다.

## 증거

| 조건 | 확인한 결과 | 자료 |
| --- | --- | --- |
| C1 | 실제 SDK single-logit worker, 사전 pair 길이·head 검사, timeout 종료, 고정 후보·예산 선택 | [tiny SDK](tiny-sdk-final.log), [SDK lock 재사용](sdk-reuse.json), [신규 시험](tests-final.log) |
| C2 | 독립 산술·span 정답, 후보 밖 정답 분모, 실패/미완전/no-answer, macro/micro, replay identity·GT 비전달 | [수기 기대값](expected.json), [89개 회귀](regression-final.log), [저장된 비교](artifacts/paired/comparison.json), [재생 보고서](artifacts/report/report.html) |
| C3 | core-only wheel, 실제 SDK 설치, sdist 재빌드/재설치, standalone stage CLI, 새 generation 경로의 fake 3-provider 시험, 실제 IAB 화면 | [설치](installation.json), [core-only](core-only.json), [sdist](sdist-replay.json), [브라우저 관찰](browser-observations.json) |
| C4 | 이전 1534개 파일과 P013/P029/P010 체크·실행 로그·grant 보존, 하네스 35개, 정확 adoption/guard, 소유 서버 종료 | [파일 보존](preservation-after.json), [제어 기록](controls-preservation.json), [하네스](harness.log), [점검](checks.json) |

89개 회귀는 기존 69개와 P020 신규 20개다. tiny SDK 시험은 별도다. 11,121개 parameter의 무작위 XLM-R classifier를 로컬에서 생성해 두 모델 profile의 실제 SDK 경로를 통과시켰다. 직접 계산 logits와 worker score가 일치한다. special token을 포함한 길이 경계, 잘못된 head의 worker 시작 전 거부, 실제 1초 cold-worker timeout·종료를 확인했다. 사전학습 모델 가중치는 사용하지 않았다.

검색 후보 provenance와 scorer 실행 종류는 별도로 저장한다. 예를 들어 `test_fixture` 후보에 none을 적용하면 후보 출처는 계속 fixture이며 scorer는 none이다. 파일/SDK 사전검사 실패는 worker0, timeout 후 계산 완료량은 null로 남긴다. 실제 시작 수와 요청/완료 pair 수를 같은 숫자로 꾸미지 않는다.

replay는 questions×variants의 정확 키 집합, 질문·본문·후보 fingerprint, method/profile/K/문자 예산, 세부 지표를 재검증한다. 질문 매핑이나 모델 identity만 바꾸고 outer manifest를 다시 봉인한 경우도 거부한다. 보고서의 지표와 개별 result.json은 같고, 기존 결과를 덮어쓰거나 모델을 다시 호출하지 않는다.

## 실패와 수정 이력

- `regression-attempt01.log`: sandbox loopback bind 제한. 승인된 소유 테스트 서버 범위에서 재실행했다.
- `regression-attempt02.log`: 기존 UI 작업의 완료 상태가 active 잠금 해제보다 먼저 보이는 경합으로 다음 요청에 busy429. 완료 게시와 잠금 해제를 같은 lock에서 처리하고, 이전 worker의 finally가 새 작업의 잠금을 지우지 않도록 수정했다. 이후 전체 회귀 PASS.
- `source-free.log`: 검증 driver를 OS 기본 Python3.9로 실행해 tarfile의 filter 인자를 사용할 수 없었다. core-only CLI 시험은 완료됐지만 sdist 단계 실패를 보존했다. 지원 Python3.12에서 새 디렉터리로 실행해 sdist 재빌드·설치·동일 보고서를 확인했다.
- 브라우저 첫 runtime은 비활성 후 초기화가 필요했다. 공식 초기 API로 새 테스트 탭을 만들었다. P029의 파일 선택창/native Codex 정책 거부 경로는 재시도하지 않았다.
- 모델명·nDCG/fact 표시 및 좁은 제목 줄바꿈을 관찰 후 보완했다. 최종 wheel로 다시 관찰했다. [UI 수정 전후 Python 바이트 동일성](final-wheel-core-equivalence.json)도 보존한다.

## 관찰 범위와 한계

같은 Mac/Python3.12 CPU, source-free 새 venv와 실제 설치 SDK, 합성 문서·주입 점수, IAB 1280×900/390×844만 검증했다. Tab 이동, Enter/Space 상세 열고 닫기, 원문 위치, 예산 제외, none/모델 미실행 상태, K>N 오류, 선택 문맥의 생성 preview를 관찰했다. 콘솔 오류와 가로 넘침은 없었다. 테스트 서버 두 개는 모두 종료했고 viewport override를 해제했다.

[MPS·다른 OS·실제 한국어 품질·사전학습 모델 메모리·실답변 품질]은 미검증이다. fixture에서 nDCG가 같아도 필수 fact 회수율이 달라지는 예를 담았지만 이를 실모델 우열로 해석하지 않는다. 답변 평가기는 N/A다. P013/P014 평가기 보류, P013 미소비 grant, P029 C4 BLOCKED를 유지한다. 이번 P020 완료가 전체 제품 goal 완료를 뜻하지 않는다.

제품 실습은 [리랭커 가이드](../../learning/rag-package/reranking.md)를 따른다. 전달 commit과 personal/dev 일치는 완료 시 delivery.json에 남긴다. main 승격·PyPI 게시·역방향 메시지는 수행하지 않는다.
