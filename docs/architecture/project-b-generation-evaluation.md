# Project B 내부 RAG Generation Evaluation 모듈

상태: 학습 범위·순서 확정, 실행 상세 계약은 초안. 2026-10-29 사용자가 제공한 Project B 설계와 “설치형 하네스 끝나고 Hybrid 전에 기본 평가기부터 만들고, NLI 비교는 그다음” 요청을 근거로 한다. 후속 사용자 정의에 따라 Project B는 HR RAG→Agentic RAG 전체이며, 이 문서는 그 내부 평가 모듈을 다룬다. A는 NL2SQL+Tool Calling, C는 Multi-Agent Orchestration이다. [프로젝트 구분](../planning/project-map.md)을 따른다.

## 위치와 학습 순서

P012까지 완료했고 설치형 하네스는 별도 프로젝트에서 관리한다. 2026-10-29 후속 사용자 요청에 따른 현재 순서는 **P015 원문 PDF 재작성 → P007 청킹·검색 실험 → P013 기본 평가기 → P014 NLI 비교 → P008 답변 비교 UI → P010 Hybrid**다. P007은 검색/fact-span 지표로 먼저 실험하므로 평가기와 순환 의존하지 않는다. P014는 비교 완료가 선행이며 NLI의 성능 우위/채택 성공을 Hybrid 착수 조건으로 강제하지 않는다.

B 내부 Generation Evaluation은 답변 생성 시스템과 독립적인 평가 모듈이다. 예정 구현 위치는 dev의 `evaluation/project_b/`이며 실제 생성은 P013 준비·채택 이후다. 큰 단계는 `1. Naive RAG/`, `2. Document Chunking/`, `3. Hybrid RAG/`로 관리하며 평가 모듈 자체에 별도 번호 폴더를 부여하지 않는다. 각 단계는 버전이 고정된 실행 결과를 export하고 평가 모듈이 읽는다. 단계 코드가 평가 모듈의 정답·rubric을 runtime import하거나 검색/생성 입력으로 사용하는 구조는 허용하지 않는다. 별도 Git 저장소 생성은 현재 계획에 포함하지 않는다.

설치형 하네스는 HR RAG P카드가 아닌 외부 선행 작업이다. P013 준비 검토에 실제 하네스 저장소·완료 commit/tag·설치/호환 검증 근거를 기록한 뒤 READY로 전환한다. 이 문서나 P012 완료만으로 하네스 완료를 간주하지 않는다. 큐의 P선행 외 이 게이트는 현재 준비 검토에서 확인하며 자동 검사로 구현됐다고 주장하지 않는다.

## 평가 1: 검증 데이터와 기본 LLM 평가기 — P013

### 실행 결과와 공통 입력

질문/질문 ID·답변/status·corpus snapshot·문서 시행일/버전·RAG 모델/digest·프롬프트/설정·run ID와 **실제 모델 전달 문맥 snapshot**을 입력으로 고정한다. 검색 전체 후보와 제외 청크는 진단용으로 별도 보존한다. 인용된 청크만 보는 평가와 전체 전달 문맥을 보는 평가를 혼합하지 않는다.

Faithfulness의 premise는 실제 전달 문맥이다. 문맥 예산 때문에 제외된 검색 청크나 Ground Truth를 근거에 넣어 점수를 올리지 않는다. 여러 청크를 결합할 때도 동일 run의 전달 snapshot 안에서만 선택하며 선택법·순서·입력 한도·잘림을 기록한다. 불충분/잘림/평가기 오류는 판정 불능으로 남기고 entailment나 neutral로 조용히 바꾸지 않는다.

### Ground Truth의 독립 파이프라인

원본 HR PDF/Markdown → 추출 검증 → 질문·기준 답변·Reference Claims 초안 → 원문 조항/페이지/span 연결 → **사람 검증·승인** → 버전 고정 저장 흐름이다. P015에서 검증한 source-v3 PDF/추출본을 기준으로 하되 P015 정책 대응표·과거 Codex rubric을 사람 승인 데이터로 승격하지 않는다. 기존15청크/P011 세트는 관찰된 자료로 표시하고 새 검증 세트와 구분한다. P015 원문과 P007 고정 청킹 후보/검색 설정을 선행으로 확보한다. P007은 P013의 답변 평가 점수를 착수/완료 조건으로 요구하지 않는다.

각 정답 claim에 원문 hash·문서 버전·시행일·근거 위치·검토 상태·실제 검토자/승인 기록을 둔다. draft/reviewed/approved를 구분하고 평가 실행에는 호환되는 approved 버전만 사용한다. 승인자는 실제 사람이며 Codex 검토를 사람 승인으로 기록하지 않는다. 승인 데이터 준비 전 코드/fixture 검증은 가능하지만 실제 평가 완료로 처리하지 않는다. 문서 개정은 새 버전과 재검토로 처리하고 다른 시점 정책을 섞지 않는다. 정답 dataset은 평가 중 자동 생성·수정하지 않는다.

### Claim Extraction과 두 평가

답변의 사실 주장을 한 번만 추출하고 양쪽 평가가 동일 claim artifact/hash를 재사용한다. 숫자·기간·대상·예외·부정을 보존하며 원답변 span에 연결한다. 복합 주장 분해·중복 제거·추출 누락/추가·비사실 문장의 처리 규칙과 독립 기대 fixture를 확정한다. 평가기의 추출 실패를 좋은 답변 점수로 바꾸지 않는다.

- **Faithfulness:** 고유 생성 claim별 entailment/neutral/contradiction 판정과 근거 span을 기록한다. 모든 필요한 판정이 유효한 경우 `지지된 생성 claim 수 / 전체 평가 대상 생성 claim 수`를 계산한다. 모순·근거 부족·판정 불능을 별도로 집계하고 전체 평균에서 실패를 제외한 분모를 숨기지 않는다. claim0인 무응답/보류에는1점을 주지 않으며 N/A와 보류 적절성을 별도 표시한다.
- **Answer Correctness:** 승인 Reference Claims와 생성 claims의 의미 대응으로 Factual Precision/Recall/F1을 Python에서 계산한다. 중복 주장으로 TP를 늘리지 않으며 표현 차이는 허용한다. 원자 claim 정규화와 일대일 매칭/동점/부분 일치 정책을 먼저 고정한다. 승인 정답 밖의 추가 주장은 자동으로 거짓이라고 단정하지 않고, 기준셋 누락 의심·참이지만 범위 밖·모순을 구분한다. 평가 중 정답 확장은 하지 않는다. precision 관점 미일치 claim과 실제 허구의 구분, 미확정 대응의 점수 보류 규칙을 확정한다.
- 유효한 확정 매칭에 대해 `P=TP/(TP+FP)`, `R=TP/(TP+FN)`, `F1=2PR/(P+R)`를 사용한다. TP/FP/FN의 원자 단위와 중복/분할 정책은 준비 시 고정한다. 0분모, 무답/보류, 정답claim0, 부분 응답, 판정 실패와 macro/micro 집계는 별도 정책·fixture로 검증한다. 비사실 텍스트나 판정 실패를 집계에서 조용히 제거하지 않는다.

### 모델과 교체 경계

사용자 제안 Qwen3-8B는 claim 추출·정답 초안·LLM 검증/매칭의 우선 검토 후보다. 현재 답변 생성 Qwen3-4B를 자동 교체하지 않는다. 역할별 prompt·schema·sampling·context·timeout·retry 정책·모델 revision/digest를 분리한다. 동일 모델 재사용은 독립 평가자라는 뜻이 아니므로 편향을 사람 검증 세트와 대조한다. Python은 산식/집계/버전/로그를 담당한다.

모델 확보·8B의 로컬 메모리/속도·라이선스·실행 라이브러리 호환성·정확한 양자화·호출량/자원 상한은 P013 준비 시 확인한다. 이번 초안 등록은 다운로드·실제 평가 실행 승인이 아니다. ClaimExtractor, ClaimVerifier, ClaimMatcher, aggregator 경계를 분리하고 NLI adapter로 검증기를 교체할 수 있게 한다.

## 평가 2: NLI 비교 — P014

초기 NLI 후보는 사용자 지정 `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`다. 모델 revision/tokenizer/label mapping/라이선스·한국어 HR 적합성·길이 제한/다중 청크 처리·실행 환경을 검증한 후 고정한다. [모델 카드](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli)의 다국어 설명이 한국어 HR 규정에 대한 검증 결과를 대신하지 않는다.

첫 비교에서는 P013에서 고정한 **동일 답변·동일 추출 claims·동일 전달 snapshot·동일 승인 정답**을 사용하고 ClaimVerifier만 LLM↔NLI로 바꾼다. 재추출/생성 모델 변경 효과를 검증기 차이로 보지 않는다. Correctness의 matcher 교체는 별도 비교 축으로 한 번에 하나만 바꾼다. 단방향 entailment가 의미 동등성을 보장하지 않으므로 양방향/부분 일치와 매칭 규칙을 먼저 검증한다.

한국어의 부정·조건/예외·수치/단위·기한·서로 모순되는 문맥·여러 청크 결합·미지지 claim을 사람이 판정한 별도 세트로 평가기 자체를 검증한다. tuning과 확인용 holdout을 구분하고 threshold를 결과에 맞춰 사후 변경하지 않는다. entailment와 contradiction이 함께 발견되는 경우의 집계, neutral/불확실/오류를 구분한다. 모델 입력이 잘리면 어떤 근거가 빠졌는지 기록하고 미검증 전체 문맥 판정으로 보고하지 않는다.

비교 결과는 claim별 혼동행렬/정확도·라벨별 P/R/F1·추출과 검증 오류 분리, 사람 기준 Faithfulness 점수 오차와 평가기 간 일치도, TP/FP/FN 매칭 정확도와 Correctness 점수 오차, 지연·메모리·호출 수·실패 유형을 포함한다. 두 평가기의 일치가 정답임을 뜻하지 않는다. 반복/순서/동시부하/cold-warm 조건과 측정 범위를 고정한다. NLI가 나쁘거나 불확실하면 LLM을 기본으로 유지하고 두 adapter와 실패 근거를 보존한다.

## 후속 재사용과 화면

P010 Hybrid와 P008 답변 비교는 B의 같은 평가 버전으로 생성 전후 run을 비교한다. P007의 검색/fact-span 지표는 그대로 유지한다. P015 원문이 후속 개정되면 B 정답의 새 버전·사람 재승인 후 P008에 연결하며 기존 정답 offset을 복사하지 않는다.

평가 모듈 기본 CLI/결과 JSON·보고서에서 질문→claims→판정→근거→산식을 추적할 수 있어야 한다. 학습 UI의 평가 메뉴/결과 연결 범위는 P013 준비 시 정하고, P008에서는 P007에서 이미 제공하는 원문·청크·검색 비교 UI에 청킹 비교 run의 답변·평가 결과를 확장한다. P007 UI는 평가 모듈 없이 동작해야 한다. 승인되지 않은 정답, 버전 불일치, 평가 미실행/오류/보류를0점 또는100점으로 표시하지 않는다. 정답과 평가 prompt가 RAG 입력으로 유출되지 않도록 검사한다.
