# P032 S2b 설치 환경 복구 및 비교 재진행 계약

2026-11-28 READY. 커밋된 실패 증거와 [준비 검토](../reviews/P032-s2b-environment-recovery-readiness-20261128.md)에 근거한 별도 복구다. 정확 채택 후 아래 환경 검증과 입력/runner 동결을 먼저 수행한다. 원래 S2b run001은 halted로 보존한다. [원래 계약](P032-s2b-nonllm-chunking-contract.md)의 실패 후 실제 추가 호출 금지는 새 READY 정확 채택 전까지 유지한다.

## 관찰한 문제

동결 `feea3c2` 이후 첫 semantic-boundary worker가 약300ms 뒤 `embedding_sdk_failed`를 반환했다. exit0은 정상 벡터 결과가 아니었으며 latch가 후속 작업을 막았다. ledger는 요청1worker/567items, completed_items=null, worker_exited/resume_safe=true를 기록한다. 색인·질문 검색 결과는 없다. 모델 품질이나 메모리 부족으로 분류하지 않는다.

모델0 import 진단은 torch의 `typing_extensions` import에서 실패했다. 설치 파일 진단은 해당 모듈·metadata 부재와 여러 불완전한 dist-info를 기록한다. 남아 있는 RECORD의 파일만 존재 검사하면 누락된 distribution 전체는 잡히지 않으므로 “남은 RECORD의 missing_count=0”을 환경 무결성 PASS로 해석하면 안 된다. 파일이 없어진 원인은 현재 미상이며 자동 정리·사용자 삭제 등으로 단정하지 않는다. 기존 다섯 SDK 버전 metadata와 wheel 파일 hash 확인만으로 실제 전체 설치를 검증하지 못한 사례다.

## 복구 범위

기존 실패 venv/run/ledger를 수정하거나 삭제하지 않는다. 새 전용 venv를 실습 workspace의 비공개 `.rag-runs/` 아래에 만들고 동일 Python 계열·동일 wheel SHA·고정 requirements lock으로 재구성한다. 시스템 Python·기존 서버·다른 프로젝트·기존 S1/S2a evidence는 변경하지 않는다. 버전 업그레이드나 모델 가중치 재다운로드를 복구에 포함하지 않는다.

설치가 필요하면 lock의 hash가 맞는 공개 SDK 배포물만 설치한다. SDK 다운로드와 모델 다운로드/추론을 구분하여 기록하며 원격 원본·실제 wheel hash·설치된 distribution 목록을 남긴다. private registry나 인증 설정을 임의로 변경하지 않는다. pip check, lock의 모든 배포물/버전 존재, RECORD의 hashed file 내용 대조, wheel의 제품 소스와 설치된 파일 대조를 수행한다. 경로 차이·생성된 entrypoint/pyc와 원본 파일의 검증 범위를 구분한다.

모델/네트워크/키 접근을 차단한 SDK import 검사와 설치 CLI/core-only 동작을 실제 worker와 같은 interpreter·정제 env에서 수행한다. torch·SentenceTransformer import 성공은 모델 적재 성공으로 확대하지 않는다. 해당 검사에서 모델 생성자를 호출하지 않는다. SDK 환경이 완전하지 않으면 실제 호출 전에 중단한다.

## 재진행 조건

동일 규정집 snapshot·질문·fact·규칙 artifact·E5 가중치/설정·semantic 파라미터·실행 순서를 보존한다. 새 interpreter와 결과 경로만 바뀌는 manifest 차이를 열거하고 비교 설정이 변하지 않았음을 확인한다. 원래 run001의 파일 hash 목록과 실패567items/1worker/완료 미확정 기록을 부모 evidence로 연결한다.

새 실행 전 독립 제어 시험과 환경 무결성 시험을 통과하고 runner/manifest를 커밋한다. 누락된 전체 distribution, 남아 있으나 내용이 변한 file, import 실패를 사전에 거부하는 시험을 추가한다. 기존 deadline/budget을 조용히 리셋하거나 같은 run을 재사용하지 않는다.

성공 경로는 새 semantic1 + index4 + query40 = 추가45workers/최대1896items다. 최초 실패를 포함하면 총46workers/최대2463requested items이며 실패567items의 완료 건수는 null로 보존한다. 이번 계약은 원래 deadline `1795808563.61378`을 연장하지 않는다. 새 환경 준비는 시작부터 최대900초이며 원래 deadline보다 늦어질 수 없다. 추가 실제45workers도 동일 원래 deadline 안에서만 진행한다. 시간 부족은 미실행/부분 실패로 기록하며 자동 새 시간창을 만들지 않는다. 복구 후 추가 기술적 실패가 발생하면 자동 재설치·재시작 없이 다시 halted와 부분 증거만 남긴다.

미검증 환경을 고친다는 이유로 LLM/생성/API/Ollama/Drive/평가기·기존 grant를 실행하지 않는다. S2b4방식 비교·source fact 지표·UI/학습 안내·기존 보존 조건은 원래 계약을 유지한다. 검토한 접수 R20261127-3674f09b의 범위만 허용하며 제품 worker의 새 진단 기능이나 SDK 버전 변경은 포함하지 않는다.

설치는 같은 wheel9342add625a9ed633dffb2fccb3bad27379e8cddaf9a06836ea5a224fe9f280a, retrieval lock SHA f7988bdf801f51e27ce7538805bd9c9ca8202c0d714c13901e53f9365891b32f다. 새 환경 준비 전 여유디스크8GiB 이상을 확인하고 runtime의2GiB 최소 여유도 유지한다. SDK 설치는 한 환경·한 고정 lock을 대상으로 하며 pip 자동 재시도0/단일 설치 프로세스·준비 deadline을 적용한다. pip 실패 시 몰래 버전/인덱스를 바꿔 반복하지 않는다. 새 정확 채택 전에는 실행하지 않는다.


## 새 child와 완료 기준

`run001` 및 이전 실패 보고서/원장/화면은 불변이다. recovery 전용 폴더에 부모 완료/증거 커밋과 전체 파일 hash 목록을 저장한다. 설치와 모델0 환경 검증에는 최대900초, 실제 비교에는 남은 원래 deadline만 사용한다. 새 시작시간을 이용해 원래 deadline을 연장하지 않는다. parent의1worker/567requested items와 child의 최대45workers/1896items를 분리하고 누적46/2463 한도를 dispatch 전에 강제한다. 완료 미확정 parent 항목을0완료로 확정하지 않는다.

child control은 원래 순서45개를 그대로 유지하고 부모 예산을 누적한다. parent 파일 변조, 환경 필수 distribution 누락/내용 변조/import 실패, 누적 budget/deadline, 두 질문 gate, 논리적 오류/출판 실패/checkpoint 실패/취소 후 추가 dispatch0을 모델 없이 검증한다. 이 복구 검증을 위해 제품의 원래 계산을 fixture로 대체하지 않는다. 현재 lock·wheel의 SDK 부품이 불완전하거나 호환되지 않으면 실제 모델 호출 전에 멈추고 별도 원인 기록을 남긴다.

기존 의미/검색 설정과 모든 입력 identity가 동일한지 확인한 후 child runner·환경 감사·manifest·시험 결과를 커밋한다. source 없는 cwd에서 새 venv interpreter로 실제 semantic1회와 네 방식40검색만 실행한다. 추가 모델 smoke/자동 반복은 없다. 단일 CPU worker/300초·관측 RSS4GiB·normal pressure·runtime disk2GiB 제한은 원래 계약을 따른다. 기존 E5 파일만 재사용하며 LLM/리랭커/모델 다운로드는0이다.

완료 증거는 환경 복구 범위/시간/설치 로그/lock과 RECORD 검증, 부모 전체 보존, 실제 결과 또는 실패/미실행, 누적 비용·작업량·자원과 소유 프로세스 회수, 원문/fact 독립 대조, source-free replay·허용 UI/학습 안내, 정상 personal/dev 전달이다. 실패 원인이 환경이었다는 사실과 복구 후 모델·검색 품질을 구분한다. 실패가 다시 발생하면 새 child를 자동 생성하지 않는다. 전체P032/goal 완료 기준은 유지하며 P013/P014·P029 C4·GT·미소비 grant는 변경하지 않는다.
