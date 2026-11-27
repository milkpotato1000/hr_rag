# P032 S2b 중단 증거

S2b는 첫 의미 경계 embedding 작업에서 중단됐다. 실제 검색 비교는 미완료이며 전체 P032도 완료가 아니다. [중단 보고서](report.html)와 [최종 보존 검사](final-checks.json)를 함께 읽는다.

## 채택과 실행

- exact READY `f12d52c99b78bfc83352c9b3e038cf08865f6d28`, adoption `192b948`, 실행 시작 기록 `4c793ff`.
- 실제 호출 전에 runner/control·독립 시험18개 PASS와 입력/설치물/모델/순서 hash를 `feea3c2`에 동결했다. [manifest](run001/manifest.json), [시험](tests-final.log), [동결 검사](freeze-checks.json).
- 초기 시험 fixture의 schema/필수 인자 오류는 tests-attempt001/002.log와 tests-diagnostic001.log에 보존했다. 수정 후15개, 최종18개가 통과했다. 실패 로그를 성공으로 바꾸지 않았다.
- [최초 실행 로그](live-run001.log), [원장](run001/ledger.json), [실패](run001/failure.json)를 보존했다. worker1개 시작·회수, 요청567항목, 완료 항목 수 미확정이다. 종료 코드0이어도 JSON은 `embedding_sdk_failed`였다.
- 시작1795804963.61378 / deadline1795808563.61378을 유지한다. 새 invocation·색인·질문 검색·자동 재시도는 없다. sampled peak RSS29,327,360byte는 짧게 실패한 프로세스의 관측값이며 모델 전체 메모리 요구량이 아니다.

## 모델 없는 진단과 재생

[SDK import 진단](sdk-import-diagnostic.json)은 모델 생성·가중치 읽기·네트워크0으로 `typing_extensions` 누락을 확인했다. [설치 파일 진단](installed-file-diagnostic.json)에서 해당 모듈이 없고25개 dist-info에 METADATA/RECORD가 없었다. 파일 누락의 원인·시점은 미확정이다. 남아 있는 RECORD의23,029개 hash 검사만으로 설치 전체가 정상이라고 판단할 수 없다. SDK 상위5개 버전과 모델 hash 사전 검사만으로 하위 의존 파일의 존재/import 가능성을 충분히 보장하지 못했다.

기존 환경을 재설치하거나 버전을 바꾸지 않았다. 복구 검토 요청 [R20261127-3674f09b](../../feedback/dev/requests/R20261127-3674f09b.json)를 `af266e8`에 먼저 커밋했다. 별도 정확 READY 전 실제 재개는 금지한다. 요청의 누적량 계산은 허용 한도 변경이 아니다.

`report_stopped.py`는 source 없는 cwd에서 기존 설치 Python의 `-I`로 실행했다. 모델 진입점을 거부하고 규칙 artifact3종을 재생했다. semantic ready artifact와 comparison은 없으며4방식×10질문을 모두 not_executed로 기록했다. branch_union/candidate_N20/topK/문맥 fact·chunk relevance·답변 지표는 모두 null이며0점이 아니다. [저장 요약](stopped-summary.json)과 [검사 로그](report-check.log)를 참고한다.

S1 3,521파일·S2a415파일·기존 보호1,513파일 hash가 그대로다. 원장 hash도 진단/재생 전후 동일하다. runner/control/입력 동결은 수정하지 않았다. P013/P014 보류, P029 C4 차단, GT·기존 실패·미소비 grant는 유지한다. 다운로드·변환·리랭커·LLM/API/Ollama/Drive/평가기·키 읽기는0이다.

## 화면 관찰

[브라우저 검사](browser-checks.json): 소유 loopback 서버에서 실제 설치 UI의 실패 작업과 기존 규칙3종만 표시됨을 확인했다. report는1280px/390px에서 문서 가로 넘침이 없고, 기본 접힌 상세를 Enter/Space로 열고 닫으며 Tab으로 다음 상세에 이동했다. 파일 선택창과 모델 실행 버튼은 사용하지 않았다. [서버 종료](ui-closed.json)는 모델0 및 소유 서버 회수를 기록한다.

- [보고서 desktop](report-desktop.jpg)
- [보고서 narrow](report-narrow.jpg)
- [설치 UI 실패 표시](installed-failure-ui.jpg)

이 화면은 저장 실패를 읽는 검증이며 실제 비교 성공을 대신하지 않는다. 다음 작업은 복구 계약 검토·정확 채택 후 별도로 결정한다.
