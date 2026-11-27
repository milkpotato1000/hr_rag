# HF 기본 모델 후보 — 출처 확인

2026-11-27 plan의 읽기 전용 조사. 사용자 방침은 인기 있는 Hugging Face 공개 모델을 기본으로 사용하고, 유료 API는 LLM 역할에만 선택적으로 연결하는 것이다. 이 문서는 후보 선정 근거이며 설치 목록 확정·다운로드·모델 실행 승인·P013 재개가 아니다. 기존 실행 순서와 P029 계약은 변경하지 않는다.

## 관찰한 후보

| 역할 | 모델·공식 카드 | 카드의 라이선스 | 인기도 관찰 |
| --- | --- | --- | --- |
| 생성/추출/LLM 판정 | [Qwen/Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) | Apache-2.0 | Hub API downloads 5,638,481, likes 2,217 |
| 소형 다국어 임베딩 | [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) | MIT | 페이지 Downloads last month 9,550,504, likes 509 |
| 다국어 임베딩 비교 | [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) | MIT | Hub API downloads 35,861,541, likes 4,043 |
| 다국어 리랭킹 | [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | Apache-2.0 | 페이지 Downloads last month 14,443,077, likes 1.32k(반올림 표시) |
| 선택 NLI 실험 | [MoritzLaurer/mDeBERTa-v3-base-mnli-xnli](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli) | MIT | 페이지 Downloads last month 250,974, likes 324 |

API 관찰 출처: [Qwen metadata](https://huggingface.co/api/models/Qwen/Qwen3-8B), [BGE-M3 metadata](https://huggingface.co/api/models/BAAI/bge-m3). 나머지는 모델 페이지 표시값이다. 조회 도구가 일부 API 본문을 반환하지 않아 그 모델들의 revision을 추측하지 않았다. 수치는 조회 시점의 표시값이며 재현 가능한 전체 Hub 순위 조사나 고유 사용자 수가 아니다. [HF 집계 설명](https://huggingface.co/docs/hub/models-download-stats)에 따르면 라이브러리별 query file의 GET/HEAD 요청을 집계하므로, 서로 다른 역할·배포 형식의 수치를 품질 순위로 직접 비교하지 않는다.

## 실행 계약으로 옮기기 전에 확인할 차이

- **Qwen**: 관찰된 원본 HF revision은 `b968826d9c46dd6066d109eabc6255188de91218`. 이것은 기존 Ollama GGUF의 digest나 그 변환 출처를 입증하지 않는다. 실제 선택 시 원본 revision, 변환본, 양자화, Ollama digest를 별도로 고정한다. 8B의 M1 16GB 실행 여유 메모리는 미검증이다. 일반 4B와 기존 Thinking 변형도 혼동하지 않는다.
- **E5-small**: 카드 기준 임베딩 384차원. 검색 질문과 문서에 각각 `query: ` / `passage: `를 사용하며 비영어 입력도 동일하다. 512토큰 제한이 있으므로 긴 청크의 잘림을 감추지 않아야 한다. 정규화·pooling·입력 정책을 index fingerprint에 포함한다.
- **BGE-M3**: 관찰된 HF revision은 `5617a9f61b028005a4858fdac845db406aefb181`. 카드에는 Dense/Sparse/Multi-vector와 최대 8192토큰 입력이 설명돼 있다. 이 모델의 모든 기능이 우리 패키지에 구현돼 있다는 뜻은 아니다. 처음 사용할 검색 출력과 길이·메모리 예산을 별도 계약으로 정한다.
- **BGE reranker**: 질문·문서 쌍을 입력해 관련성 점수를 얻는 모델이다. sigmoid를 적용한 값도 우리 데이터의 정답 확률이라고 가정하지 않는다. 같은 후보 집합에서 off/on 및 모델별 순위·지연을 비교한다.
- **mDeBERTa NLI**: 카드의 다국어 설명만으로 한국어 HR 조건·예외 판정 성능을 보장하지 않는다. label index는 고정 문자열 순서를 추측하지 말고 선택 revision의 config와 실제 fixture로 검증한다. 카드의 과거 FP16 주의 문구와 파일 dtype 표시를 곧바로 현재 런타임 지원 보장으로 바꾸지 않는다.

기본 후보는 공개 라이선스 표시를 확인했지만, 실제 배포할 revision의 라이선스 파일·변환본 조건 확인은 남아 있다. 아직 한국어 품질·추론 시간·실행 메모리·전체 패키지 통합을 검증한 카탈로그가 아니다. 새 모델을 자동으로 최신 revision으로 바꾸지 않는다.

## 학습 자료와 UI에 적용할 기준

1. 모델명 옆에 역할·공식 출처·라이선스·검증 상태를 보여주고, 인기도는 확인 날짜와 함께 참고 정보로 표시한다.
2. 선택 가능한 실제 adapter와 아직 계획 중인 모델을 구분한다. P029의 사용자 입력 form이 설치된 모델 목록이나 자동 다운로드 기능인 것처럼 설명하지 않는다.
3. 임베딩/NLI/리랭커는 기본 공개 모델 경로를 유지한다. LLM만 본인 API로 바꿀 수 있으며, 이때에도 비용·실행 여부·미측정 항목을 분리한다.
4. BM25/RRF·규칙 청킹은 알고리즘으로 설명한다. 모델 선택 표에 억지로 넣지 않는다.
5. 후속 실행 카드에서 각 모델 revision/tokenizer/전처리/의존성/자원 상한과 한국어 평가를 확정한 뒤 dev가 정확 채택한다. 이 조사만으로 P010/P020 선행을 해제하거나 추가 모델을 실행하지 않는다.
