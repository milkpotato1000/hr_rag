# RAG package 목표별 증거와 남은 작업

2026-11-27 plan 관찰. 전체 goal은 **미완료/active**다. 이전 goal turn들은 P024~P027 구현·검증/전달, P028 exact adoption, P029 실행 계약/직접 전달로 실제 상태를 진전시켰다. 2026-11-28 dev 최종78b85c8을 확인했다. P029 C1~C3는 전달됐고 C4는 도구 정책에 따른 파일 업로드 화면 관찰 차단이다. 구현/fixture/라이브/설치/화면 증거를 구별한다.

| 사용자 요구 | 현재 authoritative 증거 | 판정과 다음 행동 |
| --- | --- | --- |
| 문서 저장소 링크 입력 | P027 구현adc87a5, 완료41a469d; Drive PDF/TXT/MD·Google Docs PDF export,48테스트. OAuth SDK 실제설치/mock 인증 | 코드/모의 수집 검증 완료. 실제 사용자 계정·문서 E2E 미검증. P029 직접 링크 form 후 지정 파일/로그인 검증 필요 |
| 인기 HF 공개 모델 기본, 유료 LLM API 선택 | P024 교육 자료, P025 Ollama/OpenAI Chat/Anthropic Messages 실제 adapter,18테스트. HF 후보/라이선스 정책은 roadmap | provider 코드는 완료. 사용자 선택 모델의 실제 추론/품질·여유 메모리 미검증. 카탈로그 popularity/revision/런타임 선택 및 검증 필요 |
| 모델 선택·비교 | P025 config generation/evaluation 분리; P026 config compare, 실제 invoke 경로 | fake transport/preview 검증 완료. P029 model form/등록 설정 비교와 실제 선택 모델 비교는 남음 |
| 청킹 선택·비교 | P026 fixed/recursive/structure와 비교 CLI;36테스트. 기존 P007 semantic/LLM chunking은 별도 고정 HR stage | 일반 문서 규칙3종 완료. generic semantic/LLM 청킹 연결과 실제 실험은 남음. 기존 stage 결과를 새 module 성능으로 주장하지 않음 |
| Dense와 여러 HF embedding, Sparse, Hybrid | generic BM25는 P026. 기존 Naive/P007 Dense는 고정 모델/데이터 | P010 READY7ad76bd를 dev가 e354abd에서 정확 채택해 구현 중. 수기 순위/지표·tiny SDK 증거와 전체 회귀68개 통과 보고를 관찰. 설치·화면·완료 commit과 실제 사전학습 품질은 아직 미확인 |
| 리랭커 없음/있음·여러 방식 비교 | P020 후속계약 초안만 | 미구현. P010 다음으로 사용자 확정. 동일 후보집합/최종K·정답/지연 비교 상세 READY 준비 필요 |
| 근거 있는 최종 답변 | P026 실제 P025.invoke 호출 연결과 ID whitelist/code quote·page; fake3providerE2E 및23p합성PDF 시험 | 코드/fixture 완료. 실제 모델 답변과 의미적 근거 충실도/정답 품질 미검증. 유효 citation은 의미 정확성 보장이 아님 |
| 평가·실험 해석 | P024 가이드, P026 실패 포함 compare·N/A. P013 승인 GT/검증 일부와 보류 기록 | 일반 모듈 평가기 미연결. GT/qrels 없는 문서는N/A. P013 보류·성공1건/기존 실패/GT/grant 유지 |
| 누구나 설치해 재현 | P028 완료28c51a5, source6921810, README/artifacts/installed probes,51테스트 | 같은Mac의 core/extras/rebuilt 새venv와 wheel/sdist/init/doctor/실습 완료. 다른OS/실제 코딩 도구 UI 검증은 아직 없음 |
| Claude Code/Codex 공통 학습 | P024 요청 예시/파일규칙, P028 설치가이드 계약 | 문서 기반 경로 있음. 설치물·샘플실습은 P028 완료. 실제 두 도구 UI에서 수행한 것으로 주장하지 않음 |
| 학습용 프론트/UI | 기존 고정 HR UI는 완료. generic P029 READYe0d44e0, dev exact adoption79958fc | generic UI78b85c8 C1~C3 전달,61테스트·설치·desktop/narrow/keyboard 관찰. C4 파일 업로드 browser 관찰 미완료 |
| 단계별 폴더·P계획·이력 보존 | 기존1.Naive/2.Document Chunking 유지, 독립rag_package 선택복사provenance, P0271483파일불변 | 현재 증거 있음. 후속에서도 보존하고 P별 새 큰폴더를 만들지 않음 |

P024 완료7573c934c76aef493abb6dd1648393c025288d9c, P025 완료d7406e2b6e2c611cc741ad823d59a90bcefd6043, P026 완료0252ec1731431c67172f7692b14fed7ec763821f, P027 완료41a469dc0cae4c1cf5b963fd2da066ba443c88d4. 각 완료 시 personal/dev 일치를 관찰했다. 현재 ref가 후속 adoption으로 전진해도 이 완료 이력은 보존된다.

## 필요한 사람 결정/입력과 독립 진행

- [2026-11-28 사용자 직접 결정](rag-package-order-pending.md): 평가기 실험 보류, Hybrid→리랭커 구현 우선. 해당 순서 질문은 해소됐으며 P010 READY를 직접 전달한다.
- P013 로컬 모델 recovery 보류는 명시 재개 전 유지한다. 설치/UI/가짜 backend 검증은 이 중지와 독립이다. 준비 코드의 성공으로 보류를 해제하지 않는다.
- 실제 Drive 검증은 사용자가 지정한 접근 가능한 문서/본인 OAuth 설정이 필요하다. 실제 모델 검증은 구체적인 모델/자원·호출 범위 또는 사용자가 선택한 API 설정이 필요하다. 이것을 fixture로 대체해 완료라고 표시하지 않는다.
- main 승격/PyPI publish/새 원격은 기존 goal의 자동 부수 작업이 아니다. 승인된 personal plan/dev 증분 전달을 실제 상태로 보고한다.

P029 C4는 미완료로 유지한다. 사용자 순서 결정으로 P010의 독립 구현이 가능해졌으며 전체 goal은 다시 active다. 이번 표는 완료 체크리스트를 축소하기 위한 문서가 아니다. 최종 목표 달성은 모든 선택 축/실제 사용 경로/교육·설치·UI·검증 근거를 다시 감사해야 한다.

추가 완료 관찰: P028 완료28c51a56866f914b1745be0c1ae40a9aa215d1ad의 personal/dev 일치와 P029 adoption79958fc의 후속 진입을 확인했다. 1489파일 보존, actual model/API/Drive/user-key0. 자세한 source/artifact hash와 범위는 P028 인계/검증 기록을 따른다.

## P010 진행 및 P020 준비 관찰 — 2026-11-28

당시 P010 dev의 실행 중인 turn을 확인했다. plan의 vector byte hash/SDK identity/개별 결과 지표 일관성 검토를 dev가 수신했고 작업 중 코드에 반영한 것을 읽었다. `docs/verification/p010/hybrid-refined.log`는 독립 fixture6개 PASS, `tiny-sdk.json`은 실제 SDK의 작은 무작위384/1024차원 모델 호출과 길이 초과 거부를 기록한다. 사전학습 모델0이며 이 증거는 한국어 검색 품질을 증명하지 않는다. 기존 실패 로그도 남아 있다. 전체 회귀68개 PASS는 dev의 최신 진행 보고이며 최종 설치/화면/커밋 증거는 후속 확인한다.

P020는 아직 DRAFT다. 저장 branch 후보로 고정 N개를 구성하고 qrels를 모델 입력에서 분리하는 계약, 재검색 없는 off/on 비교와 선택 결과의 generation 연결, 필수 fact의 AND/OR span 합집합 집계를 상세 설계했다. P010 최종 artifact/API를 대조하기 전 READY나 착수로 처리하지 않는다.

## P010 완료 및 P020 READY — 2026-11-28

P010 dev/personal-dev `3d99353b5aef3b683b24d0f7fa06b8a757dc1f83` 일치와 clean/terminal turn을 확인했다. C1~C4 PASS, 회귀69개·actual tiny SDK·독립 설치·등록 합성자료 IAB 관찰·1535파일 보존이다. generic Dense/Hybrid 구현은 완료이며 실제 사전학습 한국어 성능은 미검증이다. P020는 이 최종 API/증거를 대조해 READY로 확정했다. 후보·두 scorer·qrels/facts·CLI/UI·생성 연결의 구현은 아직 남아 있다. 이전 진행 관찰은 이 완료 기록으로 갱신하며 P013/P029 보류·한계는 그대로다.
