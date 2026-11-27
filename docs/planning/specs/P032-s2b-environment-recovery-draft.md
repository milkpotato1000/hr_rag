# P032 S2b 설치 환경 복구 초안

2026-11-28 DRAFT. dev가 실행 중 실패 증거를 마감하고 있으므로 아직 실행 승인·재시도 인계가 아니다. 원래 S2b run001은 halted로 보존한다. [원래 계약](P032-s2b-nonllm-chunking-contract.md)의 실패 후 실제 추가 호출 금지는 새 READY 정확 채택 전까지 유지한다.

## 관찰한 문제

동결 `feea3c2` 이후 첫 semantic-boundary worker가 약300ms 뒤 `embedding_sdk_failed`를 반환했다. exit0은 정상 벡터 결과가 아니었으며 latch가 후속 작업을 막았다. ledger는 요청1worker/567items, completed_items=null, worker_exited/resume_safe=true를 기록한다. 색인·질문 검색 결과는 없다. 모델 품질이나 메모리 부족으로 분류하지 않는다.

모델0 import 진단은 torch의 `typing_extensions` import에서 실패했다. 설치 파일 진단은 해당 모듈·metadata 부재와 여러 불완전한 dist-info를 기록한다. 남아 있는 RECORD의 파일만 존재 검사하면 누락된 distribution 전체는 잡히지 않으므로 “남은 RECORD의 missing_count=0”을 환경 무결성 PASS로 해석하면 안 된다. 파일이 없어진 원인은 현재 미상이며 자동 정리·사용자 삭제 등으로 단정하지 않는다. 기존 다섯 SDK 버전 metadata와 wheel 파일 hash 확인만으로 실제 전체 설치를 검증하지 못한 사례다.

## 복구할 범위 후보

기존 실패 venv/run/ledger를 수정하거나 삭제하지 않는다. 새 전용 venv를 실습 workspace의 비공개 `.rag-runs/` 아래에 만들고 동일 Python 계열·동일 wheel SHA·고정 requirements lock으로 재구성한다. 시스템 Python·기존 서버·다른 프로젝트·기존 S1/S2a evidence는 변경하지 않는다. 버전 업그레이드나 모델 가중치 재다운로드를 복구에 포함하지 않는다.

설치가 필요하면 lock의 hash가 맞는 공개 SDK 배포물만 설치한다. SDK 다운로드와 모델 다운로드/추론을 구분하여 기록하며 원격 원본·실제 wheel hash·설치된 distribution 목록을 남긴다. private registry나 인증 설정을 임의로 변경하지 않는다. pip check, lock의 모든 배포물/버전 존재, RECORD의 hashed file 내용 대조, wheel의 제품 소스와 설치된 파일 대조를 수행한다. 경로 차이·생성된 entrypoint/pyc와 원본 파일의 검증 범위를 구분한다.

모델/네트워크/키 접근을 차단한 SDK import 검사와 설치 CLI/core-only 동작을 실제 worker와 같은 interpreter·정제 env에서 수행한다. torch·SentenceTransformer import 성공은 모델 적재 성공으로 확대하지 않는다. 해당 검사에서 모델 생성자를 호출하지 않는다. SDK 환경이 완전하지 않으면 실제 호출 전에 중단한다.

## 재실행 준비 후보

동일 규정집 snapshot·질문·fact·규칙 artifact·E5 가중치/설정·semantic 파라미터·실행 순서를 보존한다. 새 interpreter와 결과 경로만 바뀌는 manifest 차이를 열거하고 비교 설정이 변하지 않았음을 확인한다. 원래 run001의 파일 hash 목록과 실패567items/1worker/완료 미확정 기록을 부모 evidence로 연결한다.

새 실행 전 독립 제어 시험과 환경 무결성 시험을 통과하고 runner/manifest를 커밋한다. 누락된 전체 distribution, 남아 있으나 내용이 변한 file, import 실패를 사전에 거부하는 시험을 추가한다. 기존 deadline/budget을 조용히 리셋하거나 같은 run을 재사용하지 않는다.

성공 경로는 새 semantic1 + index4 + query40 = 추가45workers/최대1896items다. 최초 실패를 포함하면 총46workers/최대2463requested items이며 실패567items의 완료 건수는 null로 보존한다. 새로 시도할 전체 시간 한도와 설치 준비 시간을 분리해 READY에서 명시한다. 원래1시간 deadline도 이력으로 보존한다. 복구 후 추가 기술적 실패가 발생하면 자동 재설치·재시작 없이 다시 halted와 부분 증거만 남긴다.

미검증 환경을 고친다는 이유로 LLM/생성/API/Ollama/Drive/평가기·기존 grant를 실행하지 않는다. S2b4방식 비교·source fact 지표·UI/학습 안내·기존 보존 조건은 원래 계약을 유지한다. 준비 검토에는 커밋된 실패/진단/접수 기록과 정확 변경 범위가 필요하다. 계획 검토 없이 이 초안을 dev가 스스로 READY로 바꾸거나 실행하지 않는다.
