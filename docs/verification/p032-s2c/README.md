# P032 S2c 학습 진입 경로·독립 설치 검증

정확 READY `9be41de90ec370d67db4e2af4bf70e5636d5c2bf`, 채택 `c12b2e2`. 학습 시작점과 번들 안내를 현재 CLI에 맞추고 **모델·네트워크·키 읽기 0회**로 새 설치 환경을 확인했습니다. 기존 runtime·알고리즘·모델 설정 기본값은 변경하지 않았습니다.

## 사용 경로

[학습 시작점](../../learning/rag-package/README.md) → [현재 설치](../../learning/rag-package/install-current.md) → init이 복사한 START_HERE → local/API spec→llm-configure→doctor → 문서·청킹·Hybrid·선택 리랭커 → 저장 S1/S2b 비교 → 별도 설정·명시 실행 조건 순서입니다. P024 example_only JSON은 역사 참고로 분리했습니다. 독립 학습 폴더에는 plan/dev 하네스가 필요하지 않으며 기존 AGENTS/CLAUDE 규칙은 그대로 존중합니다.

## 확인한 결과

| 검사 | 결과 |
| --- | --- |
| 기존 build 도구 | 고정 lock 4개 distribution 버전·RECORD hash·import 확인. 새 설치 0회 |
| 새 wheel/sdist | 명시 allowlist 및 현재 source payload bytes 대조. 이전 실제 실험 wheel 보존 |
| 별도 core-only venv | 새 wheel `--no-deps --no-index` 설치, pip check 통과. pip와 제품만 존재 |
| source 없는 cwd | 절대 설치 Python `-I`, PYTHONPATH unset, 새 practice 폴더. checkout 모듈 대신 site-packages 사용 |
| init·doctor | resource hash 일치. 미설정 샘플은 exit3/needs_configuration, live_checks not_checked |
| 규칙 3종 | snapshot→각 build/ask→compare 실행. 비교 9행 중 6 preview, 근거 없는 unknown 질문 3행은 코드의 abstained. 모두 dispatch false·생성 0회 |
| 저장 경계 | fixed/recursive/structure chunk와 replay, frozen build/ask. semantic/LLM은 preview만 |
| local/API | 각 spec의 llm-configure→doctor→LLM validate. 키 값 없이 환경 변수 이름만 사용 |
| 준비·검색 preview | catalog/plan/prepare preview, retrieval-preview. 모델 파일 준비·SDK 설치 없음 |
| 설치된 SDK lock 경로 | 실습 cwd에서 importlib.resources로 얻은 절대경로 존재·source hash 일치. SDK 설치하지 않음 |
| 회귀 | 설치된 package를 대상으로 resource/doctor/credential 경계 3개 unittest PASS |
| 보존 | 이전 S1/S2a/S2b/recovery 및 보호 1,513파일·제품 runtime/lock 포함 7,279파일 hash 일치 |

CLI 검증 wrapper는 socket 연결/DNS·하위 process·API 키/credential 환경 변수 읽기를 거부했습니다. 생성 서버·모델 worker·UI 서버를 시작하지 않았습니다. doctor의 metadata 검사 자체가 모든 설치 파일·import를 확인한다는 뜻은 아닙니다. build 환경의 RECORD 감사는 이번 검증 코드에서 별도로 수행했습니다.

## 배포물과 근거

- 새 wheel SHA256: `87744fba87853c84a2a3c9b05b80a727c72d1113812139029210f4d664fba6bd`
- 새 sdist SHA256: `93e93e5daf8edfa795c7862f5ab57c50d714f8180d0067778605bb6ec9b404cc`
- 이전 실제 실험 wheel SHA256: `9342add625a9ed633dffb2fccb3bad27379e8cddaf9a06836ea5a224fe9f280a` (그대로 보존).
- [설치 경로·payload hash·상태](installation.json), [build 환경 감사](build-environment.json), [실행 명령/종료 코드](commands.json), [SDK lock 경로](installed-lock-path.json), [회귀 결과](resource-regression.log), [보존 목록](preservation.json), [최종 확인](final-checks.json).
- [검증 스크립트](verify.py), [네트워크·worker·키 차단 wrapper](offline_cli.py), [기존 실행의 후속 집계](finalize.py).

배포물은 로컬 독립 임시 설치 위치에 있으며 경로와 inventory는 installation.json에 기록했습니다. 재현에는 최종 확인에 기록된 source commit으로 새 wheel을 빌드합니다. 빌드 시각 등으로 archive hash는 달라질 수 있으므로 payload hash도 함께 대조합니다. PyPI나 main에 게시하지 않았습니다.

## 검증 과정의 수정과 한계

첫 검증은 CLI 명령을 마친 뒤 보고서 이름을 `summary.json`으로 잘못 가정해 중단했습니다. 실제 파일은 `comparison.json`입니다. 다음 집계는 모든 행을 preview로 기대했지만, 문맥이 없는 unknown 질문은 모델 호출 없이 abstained가 됩니다. 두 실패 로그와 당시 스크립트를 보존했고 실제 결과·dispatch·생성 수를 대조해 집계만 수정했습니다. 또한 최초 test 파일 직접 실행은 테스트 정의만 로드했으므로 명시적 unittest discovery로 3개를 실제 실행했습니다. 성공한 preview·build를 반복하지 않았습니다.

같은 Mac의 새 core-only 환경만 검증했습니다. 새 sdist는 payload를 검사했으며 sdist 재빌드·다른 OS·Codex/Claude Code 양쪽 UI·PDF extra·retrieval SDK·실서비스는 이번 시험 범위가 아닙니다. 실제 검색 재실행·가중치 다운로드·LLM/API/Ollama/Drive·평가기 0회입니다. S1/S2b의 실제 검색 관찰과 이번 모델 없는 문서 검증은 별개입니다. P013/P014 보류·GT·기존 grant·P029 C4 차단은 유지하며 전체 P032는 미완료입니다.
