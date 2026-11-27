# P032 S2b 환경 복구 준비 검토

2026-11-28 READY. [복구 계약](../specs/P032-s2b-environment-recovery-contract.md)은 기존 목표의 실제4방식 비교를 완료하기 위한 동일 버전의 격리 환경 복구다. 평가기 보류나 별도 LLM/Drive 선택을 재개하지 않는다.

접수 `af266e8076489806afd542ea012e66d4dec624a8`의 R20261127-3674f09b, 동결 `feea3c24da28a0ee3a336356daac95eb2e4027c5`, 실패 증거 `8c615d6b560dff766ccd02b172aedef36afb9cd4`, 중단 상태 `4576841c4a2c56b37430cb39f230536c1c2858b2`를 읽었다. 기존 READY f12d52c의 실패 중지를 지켰으며 자동 재시도는 없었다. 실패 보고서의 4방식×10문항 미실행/N/A 표시와 저장된 desktop 이미지를 확인했다. browser-checks는1280/390px·keyboard·설치 UI 실패 표시, ui-closed는소유서버 종료를 기록한다.

## 직접 대조한 근거

plan은 모델을 호출하지 않고 원래 manifest의 S1 3521파일, S2a415파일, 입력220파일, 보호1513파일, 동결script5개를 SHA256으로 대조해 불일치0을 확인했다. halted 원장에는 semantic1worker/567items만 있고 완료 항목은null, worker_exited/resume_safe=true다. comparison artifact가 없음을 확인했다. 종료코드0을 성공으로 집계하지 않았다.

| 증거 경로(`docs/verification/p032-s2b/` 아래) | SHA256 |
| --- | --- |
| run001/ledger.json | 65d4747ea0607e51bb938634b9548bac0b72256bcb831c29026dba891527cb85 |
| sdk-import-diagnostic.json | b897086dfccba23ddc50123903ad08a3e32d8796a3dff12d8eadc87dceadf63d |
| installed-file-diagnostic.json | 8a015bf9044d9f98e9937a83ad98352935bdc59f544ac1c7f2a9c59fcd36c307 |
| final-checks.json | ba0b355b8dedfa4356688955fbadd9a00cc1dafdd7cd8970e2baf833dd7f1e7b |
| browser-checks.json | 4a846d7620e1e340f2e143f5cbe88d84e068a677728cf47cfa0bb56098701ff9 |

SDK import 진단은 torch가 typing_extensions를 찾지 못함을 보여준다.25개 dist-info가 불완전하고 삭제 원인/시점은 미상이다. extant RECORD23029개 파일의 존재 검사는 누락된 배포물 전체를 포함하지 않는다. 이를 모든 설치 파일 내용의 hash 검증이나 설치 완전성 PASS로 해석하지 않는다. 따라서 같은 wheel·상위5종 metadata만 확인하던 preflight를 넘어 lock 전체 distribution/RECORD내용/import 검사가 필요하다.

## 변경 범위와 실행량

기존 임시 venv를 고치지 않고 workspace 비공개 전용 경로의 새 venv를 사용한다. 동일 wheel9342add... 및 retrieval lock f7988bdf...를 유지하며 새 모델 가중치 다운로드·제품 알고리즘 변경은 없다. SDK 설치 자체만 새로 허용한다. lock/hash·pip check·전체 distribution과 RECORD·worker와 같은 정제 env import를 모델0으로 통과해야 한다. 모델 생성자는 호출하지 않는다. 이 검증과 실패 fixture, child control을 커밋한 뒤 실제 실행한다.

실패1worker/567items를 보존하면서 새45workers/최대1896items가 필요하므로 누적 상한을46/2463으로 명시한다. 실제 비교 대상·원문·파라미터를 줄이지 않으며 추가 smoke는 없다. 원래 start1795804963.61378/deadline1795808563.61378은 변경하지 않는다. 준비900초와 추가 비교 모두 이 deadline 이내이며 만료되면 자동 연장하지 않는다. 준비 디스크8GiB/runtime2GiB, 단일CPU·300초·4GiB·pressure normal, 오류 후 추가dispatch0을 유지한다.

기존 control의 hardcoded 상한을 몰래 바꾸지 않고 별도 child에서 부모 누적/원래 deadline을 검사한다. 실패 후 부모 재개가 아닌 명시 검토된 새 실행이며 원래259개 부모 파일과 중단 기록을 그대로 보존한다. 새 실패는 자동 추가 child 없이 부분 결과와 원인만 보고한다. 준비/실행/보고에 대한 완료 증거와 정상 personal/dev 전달은 필요하며, 전체P032/goal 체크를 완료로 바꾸지 않는다.
