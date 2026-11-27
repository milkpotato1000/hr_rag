# P030 모델 청킹 검증

정확 READY `0c2c5d0c5d8de16702a8cd188bed078081f4b181`, 채택 `583f775`에서 구현했습니다. 기존 P020 완료 `d8724cb6b356703c8fa0d09b6d86d8e3782fdc98`를 보존합니다. 실제 사전학습 모델·LLM/API·Drive/OAuth·개인 키 호출은 0입니다.

## 구현과 출처

다섯 청킹 설정, 원문 단위/경계 artifact, 의미용 float32 벡터, LLM v2 chunking 역할, v3 frozen chunk RAG, 모델 없는 replay/derive/report를 연결했습니다. 같은 source/질문·검색·생성 설정의 2~5개 청킹 결과를 원문 fact/span으로 비교합니다. 세 provider 코드는 기존 P025 실제 transport를 사용하며 canned production 응답을 넣지 않았습니다.

선별한 P007/P026 순수 함수의 원본 커밋·hash는 [provenance](provenance.json)에 있습니다. 이전 HR runtime/ledger/grant는 가져오지 않았습니다. 실제 생성/검색/경계 실행 flag는 분리되어 있습니다. 설치 START_HERE와 resource manifest에 다섯 설정과 현재 지원 범위를 반영했습니다.

## 증거

- [최종 package 회귀](regression-final-2.log): 기존 89개와 P030 18개 경계·오류·재생·UI·회계·deadline·상한 시험. [harness 35개](harness.log).
- [독립 SDK 시험](tiny-sdk.json): 로컬에서 생성한 작은 랜덤 BERT/SentenceTransformer, 실제 encode worker·수동 document prefix 벡터 대조·공백 단위·float32 재생. [설치본 SDK](tiny-installed.json)는 source 없는 cwd에서 실제 worker 종료와 모델 없는 파생을 검증합니다. 사전학습 품질 증거가 아닙니다.
- [설치 결과](installation.json), [core-only](core-only.json), [sdist 재생](sdist-replay.json): allowlist와 wheel bytes 일치, 새 venv/소스 없는 cwd/PYTHONPATH 제거, 5방식 비교·candidate→none 연결, sdist 재빌드의 package bytes 동일. 같은 Mac에서만 검증했습니다.
- [브라우저 관찰](browser.json): 설치 wheel, 합성 backend, 1280×900 및 390×844. 390px 문서 폭 유지, Enter/Space 상세 토글과 Tab 이동, 원문 위치, LLM preview 0호출/명시 fake 3window, 82codepoint 이모지 청크, model0 derive, 후보 출처 test_fixture→none 보존. [데스크톱](browser-desktop.jpg), [좁은 화면](browser-narrow.jpg).
- [보존 검산](preservation.json): 기존 번호 단계·평가·고정 lock의 baseline bytes를 대조했습니다. P013/P014 보류·미소비 grant·GT·성공/실패, P029 C4 BLOCKED를 유지했습니다. 차단된 파일 선택창은 재시도하지 않았습니다.

첫 UI 관찰에서 선택 목록이 ID 위주인 점을 보완하여 method/크기/overlap/출처를 바로 표시했습니다. 초기 source-free 빌드와 이후 변경 전 성공 기록은 attempt 파일로 보존합니다. [unit-001](unit-001.log)의 작은 순수 fixture에 reason 필드가 빠진 실패는 fixture를 보완해 통과했습니다. [regression-001](regression-001.log)의 loopback bind 차단은 허용된 소유 fake HTTP 서버 검증 권한으로 실행해 통과했습니다. [tiny-sdk-001](tiny-sdk-001.log)의 import 경로 실패는 모듈 실행으로 수정했습니다. 실패 로그를 삭제하지 않았습니다.

## 실패와 해석

window 전체를 호출 전 검사합니다. 진단 쓰기가 deadline을 소비하면 POST를 시작하지 않습니다. SDK/file 사전 실패는 worker0이며 실제 시작 후 timeout은 worker 종료와 완료 pair/unit 미확정을 구분합니다. 초기 호출을 자동 재시도하지 않습니다. 실패/중단은 진단만 남기며 ready artifact로 선택하지 않습니다. 원자적 출판 이후 마지막 journal acknowledgement만 실패한 경우에는 이미 ready인 상태를 반환하고 진단 상태를 별도로 표시합니다.

독립 산술은 `[0,4),[4,8),[8,12)`와 벡터 `(1,0),(1,0),(0,1)`로 거리 `0,1`, 임계값/최대 길이/LLM end IDs를 검증합니다. overlap2이면 `[0,8),[6,12)`이며 중복2자, fact `[7,9)`는 두 번째 청크가 덮습니다. 공개 설정 최소 size100을 테스트 편의로 낮추지 않았습니다.

화면의 합성 LLM 경계는 38청크/중복971자로, 후보 전체 fact 회수1이 top-K/전달0으로 떨어졌습니다. 이는 의도적으로 주입한 모든 unit 종료 선택의 사례입니다. 실제 LLM이나 의미 모델의 우열로 해석하지 않습니다. 평가기·실제 한국어 품질·실서비스 메모리·정확한 token count·비용·다른 OS/두 코딩 도구 UI는 미검증입니다. 사용자 RAG 패키지 전체 goal 완료를 선언하지 않습니다.
