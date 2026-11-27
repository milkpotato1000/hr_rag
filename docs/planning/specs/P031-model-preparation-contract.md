# P031 모델 준비 실행 계약 초안

2026-11-28 DRAFT. P030 완료·최종 인터페이스와 준비 검토 전에는 실행 인계가 아니다. [발견한 공백과 공식 출처](P031-model-preparation-design.md)를 따른다. 여기서 모델 준비는 파일과 설정을 구성하는 단계이며 추론 성공·한국어 품질 검증을 뜻하지 않는다.

## 대상과 설치 흐름

초기 대상은 기존 catalog의 E5-small/BGE-M3 embedding, BGE-v2-m3/mMiniLM CrossEncoder 네 가지다. 임의 Hub repository/custom Python/GGUF를 같은 경로에서 자동 지원하지 않는다. 새 모델 추가는 catalog의 역할·구조·전처리·파일 recipe·license·revision 검토가 필요하다. LLM은 기존 Ollama/OpenAI Chat/Anthropic provider 설정을 생성하고 P030 generation/chunking 역할을 명시적으로 선택한다. 유료 embedding/reranker는 추가하지 않는다.

CLI와 한국어 가이드는 다음 단계로 이어진다. 정확 option 이름은 준비 검토에서 확정하며 실제 코어를 한 번만 구현한다.

- `model-catalog`: 네 후보·역할·공식 출처·라이선스·revision 조회 시점·준비 방식/검증 상태를 오프라인으로 표시한다. 모델 메모리와 파일 크기는 구분한다.
- `model-plan --model ID --role embedding|reranker --out DIR [--revision REF] [--fetch-metadata]`: 기본은 네트워크0 미설정 preview. 명시 metadata 조회 시 full commit SHA와 필요한 파일·크기·원본 hash·변환 여부를 고정한 준비 계획을 저장한다. branch/tag는 이 시점에 full SHA로 해소하고 실제 download가 main을 다시 따라가지 않는다. metadata만 읽는 것을 가중치 다운로드로 표시하지 않는다.
- `model-prepare --plan DIR --out DIR [--execute-download] [--execute-conversion]`: 고정 계획을 검증하고 새 디렉터리에서 작업한다. 기본 preview, download와 변환은 각각 명시 flag가 필요하다. 변환이 필요한데 flag가 없으면 가중치부터 무작정 내려받지 않고 사전 설명 후 미실행한다.
- `model-import --plan DIR --source DIR --out DIR [--execute-conversion]`: 같은 계획의 검증된 원본 regular 파일을 별도 export에 복사한다. HF cache symlink를 임의 해제하거나 원본을 수정하지 않는다. 일부 파일·revision/hash가 맞지 않으면 완료하지 않는다.
- `model-check --profile FILE`: 파일·manifest·구조만 확인하고 추론0이다. 준비 완료/SDK 미설치/추론 미검증/품질 미검증을 따로 보고한다.
- `llm-configure`: 새 파일로 provider/model/base URL/환경 변수 이름과 역할을 구성한다. local identity 조회는 명시된 Ollama 서버의 읽기 전용 정보만 사용하고, API config 생성은 키 값·유료 API 호출0이다. 기존 config를 덮어쓰지 않는다.

출력물은 `source-plan.json`, `preparation.json`, `model/`, `profile.json`을 분리한다. profile의 model directory에는 runtime이 요구하는 파일만 포함한다. 모델 준비 진단·HF cache metadata·계획은 model/ 밖에 둔다. manifest는 실제 export bytes의 SHA256으로 생성하며 사용자에게 수동 hash 계산을 요구하지 않는다. 기존 profile 직접 등록도 계속 지원한다.

## HF 준비 계획과 파일 검증

현재 검색 lock의 huggingface-hub2.5.0 설치 소스에서 model_info(files_metadata=True), snapshot_download의 revision/local_dir/dry_run/token 인자를 확인했다. 구현은 이 버전 또는 따로 검토한 고정 준비 의존성을 사용한다. 글로벌 venv를 업그레이드하지 않는다. core-only 설치는 선택 의존성 미설치를 명확히 표시하고 오프라인 catalog/설정 작성은 가능해야 한다.

공개 non-gated 모델만 token=False로 조회한다. repo ID/역할/catalog recipe, full revision, 파일별 relative path·size·LFS SHA256 또는 Git blob OID, 총 bytes, 원본 license 표시·조회 시간과 SDK 버전을 계획 hash에 넣는다. remote 파일 이름을 임의 경로로 쓰지 않으며 절대/상위 탈출/중복/잘못된 타입을 거부한다. HTTP 오류나 불완전 metadata에서 ready plan을 만들지 않는다. 부유 tag 갱신은 새 계획으로만 수행한다.

각 recipe는 config/tokenizer/pooling/필요 가중치만 고른다. native safetensors가 있으면 bin을 함께 받지 않는다. 일반 README/license는 별도 출처 기록에 보존하며 이미지/ONNX/OpenVINO/학습 코드·불필요 head 파일은 제외한다. max100파일, 원본 합4GiB/export 합4GiB를 상한으로 한다. 준비 전 여유 디스크에 원본·export·변환 임시 공간을 모두 반영하고 실제 bytes도 계속 검사한다. 새 작업 timeout·중단과 atomic publication을 마련하며 불완전 파일을 ready profile로 등록하지 않는다. 동일한 원본 캐시/다른 작업 폴더를 삭제하는 정리는 하지 않는다.

download는 고정 원본 파일과 크기/hash를 확인한 뒤 export한다. LFS는 SHA256, 일반 Git 파일은 원본 Git blob OID와 로컬 SHA256을 구분하여 검증한다. ETag를 무조건 SHA256으로 해석하지 않는다. .cache/huggingface는 export에 넣지 않는다. 일치 여부 검증이 끝나기 전 inference worker를 시작하지 않는다. 다운로드·metadata request·변환·추론 통계를 분리하고 실패 시 같은 호출을 숨겨 재실행하지 않는다. SDK의 내부 retry 정책과 실제 관찰 가능한 작업 수는 별도로 설명한다.

## BGE-M3 Dense 변환

공식 BGE-M3 main5617a9f61b028005a4858fdac845db406aefb181의 목록에는 pytorch_model.bin이 있고 safetensors는 없다. 이 모델의 Dense 기본 transformer 가중치만 선택하고 sparse_linear.pt/colbert_linear.pt는 가져오지 않는다. 변환 단계가 필요한 이유를 사용자에게 표시한다. 이 SHA는 조사 시점의 근거이며 실제 준비 계획에서 다시 metadata를 확인한다.

변환은 별도 소유 subprocess에서 고정 torch/safetensors 버전으로 수행한다. `torch.load(..., weights_only=True, map_location='cpu', mmap=True)`처럼 제한된 tensor loader를 명시하고 unrestricted pickle 또는 allowlist에 custom class를 추가하는 fallback은 금지한다. 모델 forward/custom source 실행 없이 문자열 key→지원 tensor state만 허용하여 safetensors로 저장한다. 공유 tensor storage·contiguous 처리·dtype·값/형상을 보존하는 방법과 원본/변환 후 tensor hash 검증을 구현 검토에서 고정한다. 알 수 없는 state 형식은 명시 실패다.

원본 config/modules/pooling/tokenizer와 변환된 가중치가 runtime 요구에 맞는지 검증한다. 원본 revision/file hashes와 변환 tool/version/options, 결과 hashes를 preparation 기록에 연결하고 모델 identity에 provenance를 보존한다. runtime의 bin 거부와 local-only 검사는 완화하지 않는다. worker timeout/메모리 상한·OS pressure 처리와 소유 프로세스 종료 확인은 READY 전 확정한다. tiny tensor 변환 성공을 BGE 전체 가중치 변환 성공으로 표시하지 않는다.

고정 metadata의 Dense용 필수10파일 합은2,293,315,801bytes다. [관찰 기록](../reviews/p031-bge-source-metadata.json)은 원본 크기·Git blob OID/LFS SHA256을 분리한다. 원격 metadata 확인이며 파일 다운로드·hash 재계산·변환 완료가 아니다. 실제 준비에서는 고정 revision의 metadata와 받은 bytes를 다시 검증한다. export의 새 model.safetensors는 원본 bin과 다른 파일 hash를 가지므로 동일 파일로 표시하지 않는다.

변환 fixture는 float32/float16/int64 및 contiguous/noncontiguous·공유 storage tensor를 포함한다. 저장 가능한 형태로 복제할 경우 개별 tensor의 key/dtype/shape/value hash를 변환 전후 비교한다. metadata format=pt와 출력 key 집합이 일치해야 하며 tensor에 대한 양자화/수치 cast는 하지 않는다. 원본/출력 tensor 합계와 실제 worker RSS는 다른 측정이다. SDK import·mmap·page cache 비용을 무시한 가중치 크기만으로 M1 실행 가능을 판정하지 않는다.

## 준비 작업의 자원·상태 초안

한 번의 prepare/import는 한 모델만 처리하고 동시 준비 worker는1개다. metadata 전체 deadline60초, 개별 요청 timeout20초; download 전체 deadline900초, 변환 deadline300초를 기본으로 한다. 개발 fixture 검증은 더 짧은 timeout을 주입한다. 도구는 자체 시작한 worker만 종료하고 kill 후 wait로 종료를 확인한다. Ollama나 다른 사용자의 프로세스는 종료·언로드하지 않는다.

디스크 사전검사는 원본 계획 합 S에 대해 `3*S + 1GiB`의 여유 공간을 요구한다. 원본·export·변환 임시 사본과 여유분을 위한 보수적 기준이며 실제 peak 실측값으로 설명하지 않는다. 파일별/합계4GiB·100파일 상한도 계속 적용한다. 출력은 새 경로만 허용하며 계획, 진행 중 진단, 검증된 export의 상태를 분리한다. 실패·중단 후 기존 결과나 원본을 지우지 않는다.

변환 worker는 CPU 전용이며 RSS4GiB를 중지 기준으로 삼고250ms 간격으로 관찰한다. macOS는 사전·주기 OS pressure가 warning/critical이면 시작하지 않거나 소유 worker를 중지한다. Linux는 지원되는 RSS/available-memory 관측을 별도 검증하고, 필요한 관측을 못 하면 변환 미실행으로 남긴다. RSS 표본은 GPU/통합 메모리 전체 또는 순간 peak 보장이 아니다. 기존 P013의 grant/runner를 호출하지 않고 해당 코드의 계측 의미만 참고한다. 이 초기 한도로 실제 BGE 변환이 가능한지는 live 검증 전 미확인이다. 한도를 넘어 실패하면 자동 상향하지 않는다.

진행 중 강제 종료·진단 쓰기 실패·최종 publication 실패를 각각 시험한다. READY export를 노출하기 전 원본 검증·변환 검증·profile/check 성공과 publication 의도를 기록한다. ready 파일이 이미 atomic publication 된 이후 진단 ACK 쓰기만 실패한 경우 ready artifact를 실패한 다운로드처럼 재요청하지 않으며 실제 결과와 진단 상태를 따로 보고한다. partial staging은 정상 목록에 등록하지 않는다.

## LLM 설정·설치 안내

로컬 사용자는 서버 URL·실제 모델 alias를 고르고 명시 inspect로 digest/model_info를 확인한다. HTTP 호출은 /api/tags 또는 /api/show 범위로 제한하고 /generate·/chat·/pull·서버 start/unload를 호출하지 않는다. 기존 HF 원본/양자화 매핑을 alias만으로 추측하지 않고 확인 가능한 정보와 사용자 제공 정보를 구분한다. 동일 alias가 다른 digest로 변하면 새 설정을 요구한다. P013 모델 상태/예산은 건드리지 않는다.

API 설정은 supported provider·base URL·model·max output·timeout·response mode·API key 환경 변수 이름을 검증해 config를 생성한다. 비밀값을 읽거나 실제 request를 보내지 않고 `user_configured_unverified`를 유지한다. generation/chunking/evaluation 프로필 매핑은 기록하되 생성/청킹만 선택했다고 evaluation을 실행하지 않는다. config 생성은 API 이용권 확인이 아니다.

최신 dev의 검증된 source/artifact를 선택하는 설치 안내와 독립 init 실습을 제공한다. 현재 가이드의 고정 P028 명령은 역사적 baseline으로 표시하고 최신 기능 설치 경로와 구분한다. START_HERE/doctor/UI 등록은 현재 패키지와 같은 config schema를 사용한다. 두 코딩 도구 요청 예시는 먼저 규칙을 읽고 모델 준비→실행 preview→명시 실행을 구분하며, 사람이 hash/내부 registry를 직접 편집하게 하지 않는다. 두 제품을 실제 사용하지 않은 시험을 양쪽 UI 검증으로 주장하지 않는다.

## 개발 검증과 남은 결정

원격 metadata/파일 transport fixture는 production 다운로드 코어를 통과시키며, 새로운 테스트 전용 endpoint를 배포 기본값으로 노출하지 않는다. actual SDK의 tiny safetensors 및 tiny tensor-only bin 변환·파일 hash/shape/value 일치, manifest/role/revision/symlink/path·크기/다운로드 실패/중단/출력 충돌·변환 실패·no fallback·no inference·설정 비밀값0을 검증한다. source-free 설치에서 생성한 profile을 기존 worker의 tiny 시험과 UI registry에 연결한다.

네 모델의 pinned file recipe/metadata와 변환 worker 자원·시간 초기 기준은 위에 구체화했다. 아직 LLM config 명령 schema, 고정 metadata의 준비 도구 소비 방식 및 P030 최종 artifact·resource·doctor 연결을 준비 검토해야 한다. 현재 초안의 조사/작업은 모델을 다운로드하거나 실행하지 않는다. 실제 사전학습 모델과 합성 문서로 수행할 제품 E2E는 별도 계약으로 남기며 평가기 보류를 우회하지 않는다.
