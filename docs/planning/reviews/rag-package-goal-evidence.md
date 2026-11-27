# RAG package 목표별 증거와 남은 작업

2026-11-27 plan 관찰. 전체 goal은 **미완료/active**다. 이전 goal turn들은 P024~P027 구현·검증/전달, P028 exact adoption, P029 실행 계약/직접 전달로 실제 상태를 진전시켰다. 현재 dev live turn에서 P028 구현이 진행 중이므로 완료나 차단을 추측하지 않는다. 구현/fixture/라이브/설치/화면 증거를 구별한다.

| 사용자 요구 | 현재 authoritative 증거 | 판정과 다음 행동 |
| --- | --- | --- |
| 문서 저장소 링크 입력 | P027 구현adc87a5, 완료41a469d; Drive PDF/TXT/MD·Google Docs PDF export,48테스트. OAuth SDK 실제설치/mock 인증 | 코드/모의 수집 검증 완료. 실제 사용자 계정·문서 E2E 미검증. P029 직접 링크 form 후 지정 파일/로그인 검증 필요 |
| 인기 HF 공개 모델 기본, 유료 LLM API 선택 | P024 교육 자료, P025 Ollama/OpenAI Chat/Anthropic Messages 실제 adapter,18테스트. HF 후보/라이선스 정책은 roadmap | provider 코드는 완료. 사용자 선택 모델의 실제 추론/품질·여유 메모리 미검증. 카탈로그 popularity/revision/런타임 선택 및 검증 필요 |
| 모델 선택·비교 | P025 config generation/evaluation 분리; P026 config compare, 실제 invoke 경로 | fake transport/preview 검증 완료. P029 model form/등록 설정 비교와 실제 선택 모델 비교는 남음 |
| 청킹 선택·비교 | P026 fixed/recursive/structure와 비교 CLI;36테스트. 기존 P007 semantic/LLM chunking은 별도 고정 HR stage | 일반 문서 규칙3종 완료. generic semantic/LLM 청킹 연결과 실제 실험은 남음. 기존 stage 결과를 새 module 성능으로 주장하지 않음 |
| Dense와 여러 HF embedding, Sparse, Hybrid | generic BM25는 P026. 기존 Naive/P007 Dense는 고정 모델/데이터 | generic Dense model selector·Hybrid/RRF 미구현. P010 기존 선행은 유지, 순서 변경 질문 답변 대기 |
| 리랭커 없음/있음·여러 방식 비교 | P020 후속계약 초안만 | 미구현. Hybrid 이후 선행 유지, 동일 후보집합/최종K·정답/지연 비교 필요 |
| 근거 있는 최종 답변 | P026 실제 P025.invoke 호출 연결과 ID whitelist/code quote·page; fake3providerE2E 및23p합성PDF 시험 | 코드/fixture 완료. 실제 모델 답변과 의미적 근거 충실도/정답 품질 미검증. 유효 citation은 의미 정확성 보장이 아님 |
| 평가·실험 해석 | P024 가이드, P026 실패 포함 compare·N/A. P013 승인 GT/검증 일부와 보류 기록 | 일반 모듈 평가기 미연결. GT/qrels 없는 문서는N/A. P013 보류·성공1건/기존 실패/GT/grant 유지 |
| 누구나 설치해 재현 | P028 exact adoption48434cb, READY7e92000; 아직 implementation 없음(관찰 시점) | 진행 중. wheel/sdist/독립resources/새venv/doctor/init 실제 증거 필요 |
| Claude Code/Codex 공통 학습 | P024 요청 예시/파일규칙, P028 설치가이드 계약 | 문서 기반 경로 있음. 설치물·샘플실습 완료와 실제 도구별 검증 범위를 구분해야 함 |
| 학습용 프론트/UI | 기존 고정 HR UI는 완료. generic P029 READYe0d44e0 직접 전달 | generic UI 미구현. P028 이후 실제 core/링크/model form/비교 + browser desktop/narrow/keyboard 검증 필요 |
| 단계별 폴더·P계획·이력 보존 | 기존1.Naive/2.Document Chunking 유지, 독립rag_package 선택복사provenance, P0271483파일불변 | 현재 증거 있음. 후속에서도 보존하고 P별 새 큰폴더를 만들지 않음 |

P024 완료7573c934c76aef493abb6dd1648393c025288d9c, P025 완료d7406e2b6e2c611cc741ad823d59a90bcefd6043, P026 완료0252ec1731431c67172f7692b14fed7ec763821f, P027 완료41a469dc0cae4c1cf5b963fd2da066ba443c88d4. 각 완료 시 personal/dev 일치를 관찰했다. 현재 ref가 후속 adoption으로 전진해도 이 완료 이력은 보존된다.

## 필요한 사람 결정/입력과 독립 진행

- Hybrid/리랭커 offline 구현을 평가기 실험보다 앞당길지에 대한 [질문](rag-package-order-pending.md)은 답변을 아직 관찰하지 못했다. 추천/선택 기본값/경과 시간을 승인으로 바꾸지 않는다. 현재 순서를 유지한다.
- P013 로컬 모델 recovery 보류는 명시 재개 전 유지한다. 설치/UI/가짜 backend 검증은 이 중지와 독립이다. 준비 코드의 성공으로 보류를 해제하지 않는다.
- 실제 Drive 검증은 사용자가 지정한 접근 가능한 문서/본인 OAuth 설정이 필요하다. 실제 모델 검증은 구체적인 모델/자원·호출 범위 또는 사용자가 선택한 API 설정이 필요하다. 이것을 fixture로 대체해 완료라고 표시하지 않는다.
- main 승격/PyPI publish/새 원격은 기존 goal의 자동 부수 작업이 아니다. 승인된 personal plan/dev 증분 전달을 실제 상태로 보고한다.

현재 P028·P029의 승인된 독립 구현이 있으므로 전체 goal은 막힌 상태가 아니다. 이들 실행·검증이 남아 있으며 이번 표는 완료 체크리스트를 축소하기 위한 문서가 아니다. 최종 목표 달성은 모든 선택 축/실제 사용 경로/교육·설치·UI·검증 근거를 다시 감사해야 한다.
