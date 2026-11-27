# P031 모델 준비 검증

구현 `871a0930165cb090adfc687e199f3094cc4b2eca`. exact READY 61499e4971731fbb95c41ad670ffa8a48fc30ce3, adoption c997493. [모델 준비 안내](../../learning/rag-package/model-preparation.md)와 [최신 설치](../../learning/rag-package/install-current.md)를 연결했습니다. C1~C3의 기술 검증은 PASS이며 원격 전달·최종 완료 상태는 P031 실행 로그에 기록합니다.

| 확인 | 근거 |
| --- | --- |
| 네 고정 HF recipe, plan/download/import/check, tensor-only 변환, LLM 세 역할 설정 | [최종 검사](checks.json) · [독립 테스트](../../../tests/rag_package/test_model_preparation.py) |
| 패키지 125개: 기존107+신규18 | [최종 회귀](regression-final.log) |
| 하네스35개·기존 파일1513개 보존 | [하네스](harness-run001.log) · [파일 hash](preservation.json) |
| float32/float16/int64·공유/비연속/scalar/empty/OrderedDict 실제 tiny 변환과 네 역할 export worker | [source 없는 SDK](tiny-installed.json) |
| 실제 HF SDK 객체/인자, metadata·download fake transport, 실제 owned child timeout kill/wait | [SDK 결과](tiny-installed.json) |
| core-only init/catalog/config/doctor/BM25 preview·sdist 재빌드 | [core](final-core-only.json) · [sdist](final-sdist-replay.json) |
| 생성 profile의 UI 등록·선택·합성/미검증 표시,1280/390px, 키보드 | [관찰](ui-observation.json) · [desktop](ui-desktop.jpg) · [narrow](ui-narrow.jpg) |
| 설치 payload/allowlist·문서 hash·관찰본과 최종 코드 동일 | [설치](installation.json) · [동일성](final-payload-equivalence.json) · [문서 링크](document-checks.json) |

최종 wheel SHA256 `967cd9179ed53ebccdd89d4522d33859bd0398bebb696d12b4075544124ce240`. sdist SHA256 `f736bc7b5739de529651289127833f8533436bd770fb4f2682b1ba0e8e7f9971`. 마지막 빌드는 START_HERE의 끝 빈 줄과 resource hash만 바꿨으며 실제 tiny/UI 관찰본과 모든 구현·UI bytes가 같습니다. 최종 wheel의 core-only/init와 sdist 재빌드는 다시 통과했습니다. 같은 Mac의 새 venv/source 없는 cwd이며 다른 OS·컴퓨터·두 코딩 도구 UI 성공으로 확대하지 않습니다.

변환 사본을 줄이기 위해 연속 byte memoryview를 1MiB씩 hash하고 공유/비연속 tensor만 복사합니다. 원본 참조를 해제한 뒤 출력 tensor를 하나씩 검증합니다. tiny 변환 RSS는 약197~199MiB였으며 이 수치는 약2.27GB인 실제 BGE 전체 모델의 실행 가능 근거가 아닙니다. CPU RSS4GiB·pressure·timeout 기준은 유지했습니다. Linux /proc 의미는 fixture만 검증했습니다.

실패/중간 기록도 보존했습니다. tiny-run001은 import 경로 누락, tiny-run002는 sandbox OS pressure 계측 거부로 worker 전 중단입니다. 허용된 읽기 계측으로 tiny-run003과 source-free tiny 검증이 통과했습니다. P-card 시작 로그 형식 오류는 커밋 전 수정했고 보호 규칙을 변경하지 않았습니다. 문서 링크 검사기의 공백 포함 angle-bracket 경로 처리도 수정했습니다. 중간 설치물은 installation-attempt001/002와 build 로그에 남아 있으며 최종 배포 hash와 혼동하지 않습니다.

실제 사전학습 가중치 다운로드/로드·LLM/API·Drive/OAuth·개인 키 호출은0입니다. 준비 코어의 실제 원격 전송·전체 가중치 변환·한국어 품질은 별도 live 검증 대상입니다. P013/P014 평가기 보류, GT/실패/미소비 grant, P029 C4 BLOCKED를 유지했고 파일 선택창을 시도하지 않았습니다. 검증 UI 서버는 정상 종료했습니다. 전체 사용자 goal이나 실제 제품 E2E를 완료로 표시하지 않습니다.
