# P031 모델 준비 연결 설계

2026-11-28 DRAFT. P030을 선점하지 않으며 다운로드/모델 실행 인계가 아니다. P013/P014 평가기 실험 보류, P029 C4 미완료와 기존 grant를 보존한다.

## 실제 설치 경로에서 발견한 공백

P020 완료 `d8724cb6b356703c8fa0d09b6d86d8e3782fdc98`의 embedding.py와 reranker.py는 runtime에서 regular files·고정 revision·file_manifest·safetensors를 요구한다. P010/P020 가이드는 사용자가 자체 완결 디렉터리를 별도로 준비하도록 설명하지만 이를 만드는 공통 명령이 없다. runtime에서 다운로드를 하지 않는 원칙은 유지하되 별도 준비 단계가 필요하다.

workspace.init은 배포 resources/sample을 hash 검증 후 복사한다. 관찰한 START_HERE는 P028의 규칙3종만 안내하고 최신 검색/리랭커도 미지원으로 표시했다. 이 안내의 P030 범위 정합성은 dev에 직접 전달했다. P031에서는 현재 설치본의 출처·실습·모델 준비가 하나의 흐름이 되도록 확인한다. 역사적 P028 고정 SHA와 hash는 지우지 않고 이전 검증으로 구분한다.

## 공식 배포 조사

2026-11-28 웹으로 확인한 원본 목록이며 모델을 다운로드하거나 추론하지 않았다. main은 변할 수 있으므로 실행 계약은 정확 revision과 파일 목록을 다시 고정해야 한다.

| 역할/원본 | 관찰한 관련 파일 | 준비 경로에 주는 의미 |
| --- | --- | --- |
| [E5-small](https://huggingface.co/intfloat/multilingual-e5-small/tree/main) | model.safetensors, modules.json, 1_Pooling, tokenizer 파일 | 필요한 safetensors·설정·tokenizer만 준비하여 runtime profile 생성 가능성을 검증 |
| [BGE-M3](https://huggingface.co/BAAI/bge-m3/tree/main) | pytorch_model.bin, modules.json, 1_Pooling, sparse_linear.pt/colbert_linear.pt; 목록에서 safetensors 미확인 | 공식 원본 그대로는 현 safetensors 전용 runtime 입력과 맞지 않는다. Dense만을 위한 명시 변환 경로 또는 검증된 공식 revision이 필요 |
| [BGE reranker](https://huggingface.co/BAAI/bge-reranker-v2-m3/tree/main) | model.safetensors, config와 tokenizer | single-logit 구조 검증 후 profile 생성 경로 |
| [mMiniLM reranker](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/tree/main) | model.safetensors와 bin이 함께 존재 | safetensors를 명시 선택하고 bin/ONNX/OpenVINO/학습 코드는 배포 input에서 제외 |

[HF 공식 다운로드 안내](https://huggingface.co/docs/huggingface_hub/guides/download)는 full commit revision, 파일 필터, local_dir 및 dry-run을 제공한다. local_dir에는 .cache/huggingface metadata가 생길 수 있으므로 그 디렉터리를 runtime 모델 export와 동일시하지 않는다. 원본 캐시를 수정하지 않고 필요한 regular 파일을 검증된 별도 export로 구성한다. 이 조사는 특정 SDK 버전의 API 동작을 검증한 것이 아니며 구현 시 설치 lock/API와 대조해야 한다.

## 사용자 흐름 후보

1. `models list`로 embedding/reranker의 지원 모델·라이선스·용도·준비/추론 검증 상태와 예상 파일 크기 또는 미측정을 본다. 인기도를 한국어 품질 보증으로 표시하지 않는다.
2. `models prepare`의 기본 preview에서 선택한 HF ID/revision, 가져올 파일, 다운로드 크기·export 경로·변환 여부를 확인한다. 오프라인 목록 표시와 원격 metadata 조회는 구분하고 조회 실패를 준비 성공으로 표시하지 않는다.
3. 명시 실행으로 고정 원본을 새 디렉터리에 내려받거나 검토한 로컬 원본을 import한다. 다운로드와 모델 load/추론은 별개다. 중단된 디렉터리는 ready로 등록하지 않는다.
4. 파일·구조 검증 후 manifest와 embedding/reranker profile을 출력한다. runtime은 계속 기존 local-only·hash 검사를 수행한다. 다운로드했다고 model quality가 verified로 바뀌지 않는다.
5. LLM local/API 설정에서 generation/chunking 역할을 고른다. Ollama identity의 읽기 전용 조회는 명시 선택된 서버에만 수행하고 자동 start/pull/unload는 하지 않는다. API는 model/base URL/환경 변수 이름을 설정하며 키 값을 문서·CLI 인수·Git에 넣지 않는다. 설정 생성만으로 inference를 하지 않는다.
6. init/doctor/UI 등록에서 완성된 profile을 사용하고 P030 청킹→P010검색→P020선택 리랭커→답변을 이어간다. 단계별 실행 허용과 비용은 그대로 분리한다.

명령 이름과 schema는 READY 전 확정한다. 설치를 시작하는 학습자가 model hash를 손으로 채우는 것이 기본 경로가 되지 않게 하되, 이미 검증된 profile의 수동 import도 유지한다.

## BGE-M3 변환 검토

사전학습 원본 파일 형식 문제를 숨기기 위해 다른 모델의 가중치나 tiny 모델을 BGE-M3로 표시하지 않는다. 공식 원본의 정확 revision·다운로드 파일 hash를 기록하고, 지원되는 tensor-only loader로 별도 worker에서 제한된 변환 후 safetensors로 저장하는 방식을 검토한다. custom Python/remote code를 실행하지 않고 허용된 tensor state와 원본 config/pooling만 유지한다. 원본 hash·출력 hash·변환 도구 버전과 옵션을 함께 남긴다. 기존 runtime의 bin 거부는 완화하지 않는다.

변환 지원은 별도의 실제 도구 시험·값/형상 일치 확인이 필요하다. 다운로드와 변환의 저장 공간/peak memory/timeout 한도, 실패 시 원본 및 캐시 보존을 READY에서 확정한다. 현재 DRAFT는 bin 로드나 실모델 실행을 승인하지 않는다. 원본과 변환본을 혼동하지 않는 것이 핵심이며, 정확한 지원이 불가능하면 미지원 이유를 표시하고 최종 모델 선택 요구의 미완료를 남긴다.

## 준비와 최종 검증 구분

준비 코드의 fixture 성공은 실제 모델 작동 증거가 아니다. 후속 실서비스 검증에는 고정 합성 문서·질문에서 실제 embedding/reranker/생성 연결, 순차 로딩과 자원 관찰, 저장 결과 재생과 선택 비교가 필요하다. Drive 실계정 검증에는 사용자가 지정한 문서와 인증 설정이 필요하며 API 비용 발생도 사용자가 선택한 경로로 한정한다. P013 평가기와 무관한 제품 경로라도 실제 실행 범위와 상한은 별도 계약으로 명시한다.
