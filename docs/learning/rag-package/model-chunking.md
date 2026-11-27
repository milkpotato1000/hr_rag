# 원문에서 경계를 만들고 비교하기

같은 원문을 다섯 방식으로 나누고, 저장된 청크로 검색·답변을 비교합니다. 경계 생성은 별도 작업입니다. 검색이나 보고서 조회가 청킹 모델을 다시 실행하지 않습니다. 실제 한국어 사전학습 모델의 품질은 아직 검증하지 않았습니다.

| 방식 | 경계 결정 | 오버랩 |
| --- | --- | --- |
| fixed | 고정 문자 수 | 일정 간격의 슬라이딩 창 |
| recursive | 문단·문장·공백 순서로 분할 | 기존 규칙 청킹의 왼쪽 확장 |
| structure | 제목·섹션 경계, 긴 섹션은 재분할 | 섹션 안에서 확장 |
| semantic | 인접 원문 단위의 임베딩 거리 | 기본 경계 이후 왼쪽 확장 |
| llm | LLM이 연속 단위의 마지막 ID 선택 | 기본 경계 이후 왼쪽 확장 |

의미/LLM 방식은 `base_max = size_chars - overlap_chars`를 기본 구간 상한으로 사용합니다. 새 청크의 왼쪽 확장은 직전 기본 구간의 시작을 넘지 않습니다. 원문의 공백·줄바꿈·이모지를 Unicode codepoint로 세며, 모델이 만든 문장을 청크에 넣지 않습니다. 제목과 페이지도 원문에서 얻습니다.

## 설치 샘플로 시작

[설치 안내](install.md)대로 `rag-lab init --out my-lab`을 실행한 뒤 새 폴더의 START_HERE.md를 읽으세요. 아래는 그 폴더에서 실행합니다. 출력 경로는 재사용하지 않습니다.

```sh
rag-lab snapshot --sources sources.json --out .rag-runs/snapshot-01
rag-lab chunk --snapshot .rag-runs/snapshot-01 --config chunk-fixed.json --out .rag-runs/chunk-fixed
rag-lab chunk --snapshot .rag-runs/snapshot-01 --config chunk-semantic.json --out .rag-runs/semantic-preview
rag-lab chunk --snapshot .rag-runs/snapshot-01 --config chunk-llm.json --out .rag-runs/llm-preview
rag-lab chunk-replay --run .rag-runs/chunk-fixed
rag-lab build --snapshot .rag-runs/snapshot-01 --config rag-frozen.json --out .rag-runs/index-01
rag-lab ask --run .rag-runs/index-01 --config rag-frozen.json --question '생일 휴가 자격은?' --out .rag-runs/answer-01
```

규칙 청킹은 즉시 저장합니다. 의미/LLM 명령은 기본적으로 단위·예상 요청·프롬프트만 미리 보여 주며 검색 입력으로 쓰지 않습니다. 실제 경계를 만들 때만 새 출력 경로와 `--execute-chunking`을 사용합니다. 샘플의 모델명·revision·digest·파일 manifest는 미설정 표시이며 실행 성공을 뜻하지 않습니다. 다운로드나 모델 서버 시작은 자동 수행하지 않습니다.

## 두 모델 방식의 의미

의미 청킹은 E5/BGE의 **document 전처리**로 각 단위를 임베딩합니다. 이웃 거리 `1 - cosine`가 임계값 이상이고 현재 구간이 최소 길이 이상이면 자릅니다. 다음 단위를 추가해 최대 길이를 넘는 경우에도 자릅니다. 거리는 문서 안에서만 계산합니다. float32로 저장한 벡터에서 최초 경계를 계산하므로 재생과 최초 결과가 일치합니다. 단위 임베딩과 검색용 완성 청크 임베딩은 별도 비용입니다.

LLM 청킹은 원문 단위 ID·본문·구간 상한을 받습니다. 질문·정답·qrels는 청킹 프롬프트에 들어가지 않습니다. 응답은 `{"end_unit_ids":["..."]}`만 허용하며 마지막 단위 ID를 포함해야 합니다. 재작성, 알 수 없는 ID, 역순·중복, 길이 초과, 잘린 JSON, refusal/tool use는 실패입니다. 출력 경계로 원문을 잘라 청크를 만들므로 LLM이 사실을 덧붙일 수 없습니다.

LLM 설정 schema v2는 `generation`, `evaluation`, `chunking` 역할을 모두 명시합니다. 기존 v1 설정은 기존 두 역할로 계속 작동하지만 청킹 호출에는 역할 미설정 오류를 반환합니다. 생성 모델을 UI에서 바꿔 저장해도 평가·청킹 프로필은 보존합니다. [provider 안내](providers.md)를 함께 읽으세요.

## 크기와 실패를 읽는 법

`size_chars`는 100~4000, overlap은 0~min(400,size-1)입니다. 단위 최대 5000개, 출력 청크 최대 10000개입니다. LLM window는 한 문서의 연속 단위만 담으며 window 수·문자·단위 수·실제 요청 JSON byte 한도를 모두 첫 호출 전에 검사합니다. 정확한 토큰 수는 N/A입니다. 문자/byte 한도는 모델 token window를 보장하지 않습니다.

전체 deadline은 첫 모델 작업 직전에 시작하며 각 HTTP timeout은 남은 시간보다 길지 않습니다. 자동 재시도는 0회입니다. 두 번째 window가 실패하면 세 번째를 보내지 않습니다. timeout의 서버 처리 여부가 불명확하면 `outcome_unknown`을 보존합니다. 로컬 기록만으로 원격 처리가 중지됐다고 주장하지 않습니다.

`출력명.invocation-.../invocation.json`은 호출 전 생성되는 진단 기록입니다. 준비·실제 전송·성공·실패·미확정·usage를 구분합니다. 실패한 실행은 ready 청크가 되지 않으며 다시 시작해도 자동 재개하지 않습니다. 출판 직전 기록 쓰기가 실패하면 ready 경로는 없습니다. 원자적 출판 후 마지막 진단 확인 쓰기만 실패한 경우에는 이미 검증·봉인된 ready artifact가 기준이며 결과에도 그 상태가 표시됩니다. 새 요청을 보내지 않습니다.

## 저장 결과를 파생하고 비교

`chunk-derive --run 저장청크 --config 새설정 --out 새경로`는 모델 호출 0회입니다. 의미 방식은 같은 단위·모델·전처리·저장 SDK identity의 벡터로 임계값/길이 정책을 바꿀 수 있습니다. overlap만 변경하면 기본 경계를 유지합니다. LLM 파생은 원래 unit/window/prompt/경계를 유지하고 overlap·충분한 출력 크기만 바꿉니다. 새 크기를 초과하면 `derived_size_exceeded`로 실패하며 청크를 몰래 줄이지 않습니다.

RAG v3 설정은 `chunk_artifact` 경로와 retrieval/embedding_config/llm_config만 가집니다. 기존 inline 청킹 v1/v2 설정도 유지됩니다. 같은 snapshot과 검색·생성 설정의 v3 파일 2~5개, 질문 1~20개로 비교합니다.

```sh
rag-lab compare --snapshot .rag-runs/snapshot-01 --configs fixed-v3.json semantic-v3.json --questions questions.json --out .rag-runs/compare-chunks
rag-lab chunk-report --run .rag-runs/compare-chunks --out .rag-runs/chunk-report
```

`fixed-v3.json`과 `semantic-v3.json`은 rag-frozen.json 사본에서 저장 청크 경로만 바꾼 파일입니다. 의미 artifact는 별도 경계 실행 후 ready여야 합니다. Dense/Hybrid를 쓰면 `--execute-retrieval`이 필요합니다. 생성은 `--execute`를 따로 선택합니다. 비교 중 청킹 모델이나 리랭커를 암묵적으로 실행하지 않습니다.

`--facts`는 [리랭킹 안내](reranking.md)의 source fact/span schema를 사용합니다. 동일 원문 구간을 여러 청크의 합집합으로 덮는지 검사하므로 청크 ID가 달라도 비교할 수 있습니다. 후보 전체·top K·전달 문맥의 fact recall/all_required, 질문별·macro/micro·유효/실패/필수 없음 분모를 봅니다. 원문 회수는 답변의 정확성 평가가 아닙니다.

청크 qrels가 필요하면 `--qrels`에 `{"schema_version":1,"by_chunk_fingerprint":{"해당 fingerprint":{기존 qrels 객체}}}` 파일을 넘깁니다. 각 fingerprint에 별도의 정답을 제공하며 다른 청킹의 라벨을 가져오면 거부합니다. 없는 라벨은 N/A입니다. 질문·설정·결과 매핑과 지표는 보고서 재생 시 모델 없이 다시 검증합니다.

## 학습 화면과 최적화 순서

serve에 `--chunk-config`를 다섯 번 지정해 설치 샘플을 등록하세요. 화면에서 원문 → 단위 → 기본 경계 → 오버랩 청크 → 검색 색인 순서로 살펴봅니다. 청크 선택 비교는 공통 검색·생성 설정을 사용합니다. 답변 상세를 열면 그 결과의 후보를 P020 리랭커 흐름으로 고정할 수 있습니다.

1. 원문 파싱이 빠짐없이 되었는지 먼저 확인합니다.
2. 필수 조건이 경계 양쪽으로 갈라지는 사례를 찾습니다. overlap과 청크 크기 하나씩 바꿉니다.
3. 후보에 근거가 없으면 검색을, 후보에는 있는데 전달되지 않으면 K/문자 예산을 점검합니다.
4. 전달 문맥에 있는데 답변이 누락하면 생성 단계의 문제로 분리합니다.
5. 같은 근거 회수율이라면 청크 수·중복 문자·단위 임베딩/색인/질문/생성 작업량을 비교합니다.

test_fixture 경계의 출처는 파생·후보·none/리랭커 이후에도 유지합니다. 실제 SDK tiny 랜덤 가중치 시험과 fake provider 시험은 연결 검증이며 한국어 실제 품질 증거가 아닙니다. 모델 비용은 측정하지 않았습니다. [Hybrid 안내](hybrid.md), [화면 안내](ui.md)에서 다음 실습을 이어갈 수 있습니다.
