# 모델 준비부터 실습 연결까지

이 경로는 사람이 revision과 파일 hash를 수작업으로 입력하던 단계를 줄입니다. 공개 embedding/reranker 파일 준비와 LLM 설정 생성을 분리합니다. **준비 완료는 추론 성공이나 한국어 품질 검증이 아닙니다.** [최신 설치](install-current.md) 후 새 workspace의 START_HERE.md를 따라갑니다.

## 1. 오프라인 계획

```sh
rag-lab model-catalog
rag-lab model-plan --model intfloat/multilingual-e5-small --role embedding --out .rag-runs/e5-plan
rag-lab model-prepare --plan .rag-runs/e5-plan --out .rag-runs/e5-ready
```

catalog와 기본 plan/prepare는 네트워크·키·추론 요청 0입니다. 배포된 metadata의 관찰일은 2026-11-28이며 실제 다운로드 검증과 구분합니다. `source-plan.json`은 고정 commit SHA, 파일 목록·크기·Git blob OID/LFS SHA256, 변환 방법을 봉인합니다. `--revision main`만 넣으면 unresolved preview입니다. `--fetch-metadata`를 명시하면 공개 HF metadata를 조회해 새 full SHA 계획을 만듭니다. 기존 계획을 자동 갱신하지 않습니다.

| 역할 | 지원 모델 | 준비 방법 |
| --- | --- | --- |
| embedding | intfloat/multilingual-e5-small | native safetensors 복사 |
| embedding Dense | BAAI/bge-m3 | tensor-only bin → safetensors 변환 |
| reranker | BAAI/bge-reranker-v2-m3 | native safetensors 복사 |
| reranker | cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 | native safetensors 복사 |

임의 HF 모델·custom Python·GGUF·유료 embedding/reranker는 이 준비 경로에서 지원하지 않습니다. BGE-M3의 sparse/ColBERT head는 받지 않습니다. 모델별 라이선스·공식 출처는 catalog에서 확인합니다.

## 2. 명시 파일 준비

아래는 사용자가 실행을 선택할 때의 명령입니다. 이번 개발 검증에서는 실제 사전학습 파일 다운로드·로드를 수행하지 않았습니다.

```sh
rag-lab model-prepare --plan .rag-runs/e5-plan --out .rag-runs/e5-ready --execute-download
rag-lab model-check --profile .rag-runs/e5-ready/profile.json
```

이미 같은 계획의 원본 regular 파일이 있으면 `model-import --plan .rag-runs/e5-plan --source /원본폴더 --out .rag-runs/e5-import`를 사용합니다. 원본은 수정하지 않으며 HF cache symlink는 거부합니다. BGE-M3는 prepare/import 모두 `--execute-conversion`이 추가로 필요합니다. 변환 승인이 없으면 다운로드도 시작하지 않습니다.

출력의 `model/`에는 runtime 파일과 출처 sidecar만 들어갑니다. 계획·진단·profile은 별도 파일이며, profile의 상대 `model` 경로와 export bytes의 SHA256을 자동 작성합니다. source-provenance.json도 manifest에 포함됩니다. 원본 bin hash와 변환 safetensors hash는 서로 다릅니다. 변환은 CPU, weights_only, mmap, 고정 torch/safetensors를 사용하고 문자열 key→tensor의 dtype·shape·값을 보존합니다. 공유 storage/비연속 tensor만 복사하며 forward는 실행하지 않습니다.

다운로드는 고정 revision의 필요한 파일만 요청합니다. LFS는 SHA256, 일반 파일은 `blob <크기>\0` 헤더를 포함한 Git OID로 검증합니다. 원본 합계/최종 export는 각각 4GiB·100파일 이하여야 합니다. 디스크 여유 기준 `3 × 원본 크기 + 1GiB`는 보수적 사전 기준이며 peak 실측값이 아닙니다.

한 사용자에게 준비 작업은 한 번에 하나입니다. metadata 60초/개별 20초, 다운로드 900초, 변환 300초 한도가 적용됩니다. 변환 RSS 4GiB, 250ms 관측, macOS warning/critical 또는 계측 실패 시 중지합니다. Linux는 RSS와 available-memory 관측을 사용하며 실제 다른 OS 검증 여부는 증거에 별도로 기록합니다. 표본 RSS는 순간 peak·GPU·시스템 전체 메모리 보장이 아닙니다. 이 한도로 실제 BGE 전체 변환이 가능한지는 미검증입니다.

실패 시 새 출력은 ready로 게시되지 않으며 sibling `.preparation.json` 진단과 숨김 staging을 남깁니다. 자동 재시도는 없습니다. 이미 게시된 결과의 진단 ACK만 실패하면 ready 결과와 `ack_write_failed`를 함께 반환합니다. 원본/다른 작업/공유 캐시는 삭제하지 않습니다. download/metadata의 상위 작업 수와 SDK 내부 HTTP retry는 다릅니다. 정확히 관찰하지 못한 SDK HTTP 횟수는 미확정입니다.

## 3. LLM 역할 설정

샘플 `llm-spec-local.json`, `llm-spec-api.json`, `llm-spec-mixed.json`을 복사해 모델·URL·원본 정보를 입력합니다. 세 역할 generation/evaluation/chunking은 반드시 실제 profile 이름을 가리켜야 합니다. mixed는 답변을 API, 청킹을 local로 설정하는 예시입니다.

```sh
rag-lab llm-configure --spec llm-spec-local.json --out llm-preview.json
rag-lab doctor --llm-config llm-preview.json
```

기본 local 출력은 digest 0과 `example_requires_configuration`으로 실제 실행을 막습니다. 서버가 이미 준비된 경우 새 출력 경로와 `--inspect-local`을 지정하면 해당 local 모델의 `/api/tags`, `/api/show`만 읽습니다. 고유 서버/모델당 최대 2회, 각 5초, 전체 60초, 재시도 0입니다. 모델 pull/start/chat/generate/unload는 하지 않습니다. HF 원본·revision·양자화는 사용자 입력으로 분리하며 alias로 추측하지 않습니다. 서버 identity 확인 후에도 품질은 미검증이고 실제 실행 시 digest를 다시 확인합니다.

API 설정은 키 환경 변수 이름만 저장하며 키 값·header·임의 request body를 받지 않습니다. 생성 중 키·API 호출은 0이고 `user_configured_unverified`입니다. 설정의 evaluation 역할은 평가기 실행 허가가 아닙니다. 기존 파일을 덮어쓰지 않습니다.

## 4. doctor와 UI

```sh
rag-lab doctor --llm-config my-llm.json --embedding-config .rag-runs/e5-ready/profile.json --chunk-config chunk-semantic.json
rag-lab serve --workspace . --sources sources.json --llm-config my-llm.json --embedding-config .rag-runs/e5-ready/profile.json
```

semantic/LLM chunk 설정의 참조도 생성한 profile/config 경로로 바꿉니다. 준비 profile은 기존 build/검색/리랭커 옵션에서 그대로 사용합니다. UI는 등록된 설정 선택, 준비 출처 기록, 미검증 상태를 표시합니다. 내부 registry JSON을 편집하지 않습니다. 전체 weight hash 재검증은 명시 `model-check`로 수행하며 UI의 출처 기록 확인과 구분합니다. 실제 모델 실행 flags는 준비와 별개이며 기본 서버는 preview입니다.

`doctor` exit0은 offline 설정 검사 통과, exit3은 placeholder 설정 필요, exit2는 잘못된 설정/지원 환경 문제입니다. 역할 상태와 SDK 설치/버전 상태를 별도로 읽습니다. SDK가 없어도 catalog·설정 생성은 가능하지만 실행에 필요한 SDK를 설치해야 합니다. 기본 doctor는 HTTP·키·weight load가 0입니다.

## 코딩 도구에 요청하기

Codex와 Claude Code 모두 다음 순서를 요청할 수 있습니다. 두 도구 UI를 실제 사용했다는 검증은 아닙니다.

> 이 프로젝트 AGENTS.md/CLAUDE.md와 현재 plan/dev 규칙을 먼저 읽어 주세요. 기존 상태를 보존하고 지원 catalog로 모델 준비 계획을 만드세요. 기본 preview에서 필요한 파일·변환·자원을 설명하고, 명시한 다운로드/변환만 실행하세요. 생성 profile을 doctor/model-check로 확인한 뒤 기존 RAG 설정과 UI 등록 인자로 연결하세요. 추론은 별도 preview 후 명시한 범위에서만 실행하며 평가기 보류는 유지하세요. 파일 hash와 registry는 수작업으로 채우지 마세요.

[검증 기록](../../verification/p031/README.md)에는 실제 tiny SDK와 fake transport, 실제 사전학습 모델 미검증을 구분합니다.
