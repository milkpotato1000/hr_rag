# P032 실제 RAG 통합 검증 설계

[전체 목표의 남은 검증과 학습 문서 상태 감사](../reviews/P032-package-completion-gap-audit-20261128.md)는 S1/S2a 완료와 S2b 진행을 전체 완료에서 구분한다. 새 실행 범위를 승인하는 문서는 아니다.

2026-11-28 전체 설계. S1 실제 검색 검증·S2a 청킹 준비 완료 이후 S2b 실제4방식 청킹 비교를 별도 READY로 추가했다. 각 범위의 정확 채택 후 실행하며 LLM 청킹·답변 생성·S3 계정 연결은 DRAFT로 유지한다. P013 평가기·로컬 메모리 recovery 보류를 우회하지 않는다.

## 고정 자료와 질문

기존 `2. Document Chunking/data/source-v4/output/pdf/hr-handbook.pdf`를 후보로 선택했다. 실제 파일은227474bytes, SHA256=1a199799cc3807fdaa6e0390784d58697d38a83d4708b2967ddead72dc4f9369다. 기존 P007 source-profile은23쪽·canonical38582문자·79제목을 기록한다. 이는 기존 파서의 관찰값이며 새 generic snapshot에서 같은 canonical/offset이라고 가정하지 않는다. 설치물로 다시 파싱하여 페이지·제목·원문 누락·정규화 차이를 대조해야 한다.

run004의10개 질문·필수/보충 주장과 별도의 P013-human-approval.json을 읽기 전용 참고로 사용한다. packet 내부 후보 status는 당시 검토 이력이며 이후 승인 기록과 구분한다. packet 파일 SHA256=e081e372ff089b5ad6eae334b29924438359993fdfa534d67578af9785b1aa7b, 승인에 연결된 내부 packet_sha256은 별도 필드다. 파일 bytes hash와 내부 digest를 혼동하지 않는다. 승인된 GT를 수정하거나 평가기를 실행하지 않고, 각 질문의 근거 문장·조항을 새 snapshot의 exact source span으로 다시 연결한다. 이전 canonical offset을 그대로 복사하지 않는다.

직접 대조한 내부 packet_sha256은 ddbc3975cc2dd728bc6950fed1a507ed03223cbdea94987c572b6cc2f0bde235이며 승인 기록의 run004_packet_sha256과 일치한다. 기존 승인을 새 모델의 출력 품질 승인으로 확대하지 않는다.

[기존 근거 감사](../reviews/p032-source-fact-audit.json)는 필수38개 주장의 old canonical slice와 quote/hash가 모두 일치함을 확인한다. 15개 주장이 같은 질문 내 다른 주장과 source quote를 공유하고,10개 quote는30자 미만이며2개는140자를 넘는다. 이 길이 표시는 자동 오류 판정이 아니라 재매핑 검토 대상 표시다. 동일 인용문을 쓴다고 서로 다른 승인 사실을 중복으로 제거하지 않는다. 반대로 한 문단 전체를 각 fact의 최소 근거로 그대로 사용하면 일부 사실만 회수한 상황을 구별하기 어려우므로 질문별 충분한 근거 구간을 검토한다.

예를 들어 gt01의 재직 기간·연간 일수·수습 제외는 별도 fact로 유지한다. 원문 조항/대상 맥락을 보존하면서 해당 조건을 지지하는 구간을 각각 정한다. gt04의 짧은 “승인 여부와 별개다”는 주어/대상이 다른 문장에 있으므로 단어 조각만 회수했다고 충분한 근거로 판정하지 않는다. 여러 구간을 함께 필요로 하면 P020 facts의 한 alternative 안에 spans를 묶어 AND, 독립적으로 충분한 다른 근거가 있으면 alternative 간 OR로 기록한다. 행정 설명까지 무조건 모든 fact의 필수 span으로 넣거나, 평가 점수를 올리려고 예외/부정을 삭제하지 않는다. claim 의미/필수·보충 정책 변경이 필요하면 기존 승인과 별도 결정으로 남긴다.

gt09/gt10은 required_facts가0인 질문이다. 이때 fact recall은 no_required_facts/N/A이며1이나0으로 바꾸지 않는다. 근거에 없는 전기요금 한도·킬로미터당 지급액을 지어내는지, 근거 부재를 설명하는지는 별도의 답변 검토 항목이다. 빈 fact 목록 자체가 올바른 보류 답변을 증명하지 않는다. 새 snapshot과 qrels/facts가 아직 생성되지 않았으므로 이 감사 자료를 runtime 정답 파일로 직접 읽지 않는다.

처음 검증은 질문 수를 줄인 smoke와 전체10개를 구분한다. smoke 성공만으로 전체 비교를 완료하지 않는다. 검색 관련성 qrels와 원문 필수 fact/span은 generation/NLI 프롬프트에 넣지 않으며 검색·리랭킹 성능 및 전달 문맥의 누락을 측정하는 데 사용한다. 새로 작성하는 qrels는 작성/검토 근거를 별도 남긴다.

## 순차 검증 후보

| 단계 | 고정할 것과 바꿀 축 | 확보할 증거 |
| --- | --- | --- |
| A 준비 | P031의 고정 revision·파일 recipe, 독립 설치 | 원본 hash·native/변환 출처·검사·소요 시간·디스크·자원·실패. 실제 다운로드와 tiny fixture를 구분 |
| B 검색 기준선 | 같은 snapshot·규칙 청크·질문, E5-small/BGE-M3와 BM25/Dense/Hybrid | 실제 index/query 전처리·차원·원본 근거·qrels 지표·실패·cold 지연. 작은 모델부터 단독 실행하고 종료를 확인 |
| C 리랭커 | 같은 저장 후보 N·K·문맥 예산, none/mMiniLM/BGE | 후보 밖 재검색0, 실제 pair 점수·순위·top-K/문맥 근거 회수와 시간·메모리 비교 |
| D 답변 | 동일하게 저장된 전달 문맥, 선택된 local/API 생성 profile | 실제 request identity·답변·인용·에러/보류, 질문의 필수 항목과 원문을 대조한 검토. 자동 Faithfulness/Correctness 평가기는 실행하지 않음 |
| E 청킹 | 같은 source·질문·검색/생성 profile, fixed/recursive/structure/semantic/LLM | 실제 경계·overlap·원문 보존·중복·근거 회수·작업량, 모델0 replay/derive. 경계 생성 비용과 검색/생성 비용을 분리 |
| F 사용자 경로 | 선택한 결과를 설치 CLI/UI에서 재생하고 코딩 도구 실습으로 연결 | 문서 링크·모델 설정→최종 답변 경로, 허용 UI 검증·설치 출처·실패 복구와 지원 한계 |

모든 축을 곱한 무제한 실행은 하지 않는다. 대표 기준선을 고정하고 한 축씩 바꾸는 행렬·최대 작업 수를 READY 전에 산출한다. E5/mMiniLM만 통과했다고 BGE/LLM 청킹의 실제 성능까지 검증했다고 쓰지 않는다. 큰 모델이 자원 한도를 넘으면 해당 상태를 실패/미지원 환경으로 명시하고 입력 축을 몰래 다른 모델로 바꾸지 않는다. 성공 threshold를 보고 난 뒤 유리하게 바꾸지 않는다.

## 실제 모델과 권한 경계

embedding/reranker는 P031 네 공식 후보와 pinned recipe를 사용한다. CPU 단일 owned worker, 고정 SDK·batch1·작은 token 한도로 시작하고 actual RSS/OS pressure·경과 시간·worker 종료를 관찰한다. 전체 PDF·모든 질문으로 늘리기 전 작은 사례를 검사한다. 한도·사전 여유 조건·업무/제어 요청 수·전체 deadline은 P031 구현과 현재 환경을 대조해 READY에서 확정한다. 다운로드 완료와 메모리 적재를 구분하고 다른 앱을 종료해 여유 공간을 만드는 방법은 쓰지 않는다.

생성 모델의 기존 qwen3:4b alias는 과거 lock에서 Qwen3-4B-Thinking-2507 원본을 가리키므로 일반 Qwen3-4B와 혼동하지 않는다. 과거 digest만 복사해 현재 서버/실행 가능을 입증하지 않는다. 새 P031 inspect 결과와 실제 선택·설정이 필요하며, 모델 pull/start/unload·8B probe·기존 grant 소비를 이 초안에 포함하지 않는다. 로컬 생성·LLM 청킹 실행 범위와 P013 중지 경계를 READY 전에 명시한다. API는 사용자가 선택한 모델·자격/예산으로만 호출하며 키 값은 문서/CLI 인수/Git에 남기지 않는다. 키가 없으면 해당 실제 API 검증은 미실행으로 남기고 fake 결과를 실호출로 표시하지 않는다.

Google Drive 실제 연결은 사용자가 지정한 테스트 문서와 본인 인증 설정이 필요하다. 현재 링크 질문은 답변 대기이며 예제 placeholder를 실제 연결로 간주하지 않는다. 로컬 규정집 시험과 독립 진행하되 로컬 파일 성공으로 웹하드 링크 E2E를 완료하지 않는다. P029 차단된 filepicker 경로도 그대로 미완료로 두고 정책을 우회하지 않는다.

## 다음 준비 작업

### 선택 대기와 독립 준비의 분리

생성 profile과 Drive 링크가 미정이어도 전체 준비를 멈추지는 않는다. P032의 최종 범위는 유지하고 아래 단계별로 실행 범위를 분리한다. S1/S2a 완료 후 S2b 실제4방식 비교를 추가 READY로 확정했으며 LLM·생성·계정 연결 대기는 유지한다.

1. **S1 공개 검색 모델과 규정집:** P031 완료 설치물에서 고정 로컬 PDF의 새 snapshot·fact/qrels 매핑을 준비하고 E5/mMiniLM부터 실제 파일 준비·검색·리랭킹을 검증한다. 이후 같은 조건의 BGE 두 모델까지 비교한다. 사용자 API 키·Ollama 생성·평가기·Drive 계정은 사용하지 않는다. 실제 다운로드/CPU 추론의 요청 수·시간·자원 한도와 중단·worker 회수 검증을 확정한 뒤에만 READY로 인계한다.
2. **S2 답변과 LLM 청킹:** 사용자가 선택한 local/API 경로와 실제 identity를 확정한 뒤 생성 모델 비교 및 LLM 경계 비교를 실행한다. S1의 동결 후보·문맥을 재사용하여 검색 차이와 생성 차이를 구분한다. 선택 답변이 없으면 이 단계만 미착수로 유지한다.
3. **S3 사용자 문서 연결과 실습 재현:** 지정된 테스트 링크·사용자 인증으로 문서 연결을 검증하고 설치 CLI/UI 및 Codex/Claude Code 실습 결과를 대조한다. S1의 로컬 PDF 성공으로 이 단계를 대체하지 않는다.

S2의 선택 의존 작업과 별개로 [S2a 청킹 사전 준비](P032-s2a-chunking-preparation.md)를 추가 READY로 확정했다. 동일 snapshot의 규칙3종 artifact와 semantic/LLM preview·작업량을 모델 호출0으로 준비하는 범위다. [준비 검토](../reviews/P032-s2a-readiness-20261128.md)의 정확 채택 전 실행하지 않으며, 실제 semantic/LLM·답변 비교를 이 사전 준비로 대체하지 않는다. 생성 profile과 Drive 링크에 대한 기존 질문은 계속 대기한다.

S2a 완료17ea630의567unit/규칙201·257·264chunks를 바탕으로 [S2b 실제4방식 비교 계약](P032-s2b-nonllm-chunking-contract.md)을 READY로 확정했다. [준비 검토](../reviews/P032-s2b-readiness-20261128.md)에 E5 semantic 경계와 동일 Hybrid 검색의 최대45worker/1896항목·1시간·4GiB, 단일 invocation·실패 latch·중간 결과 보존을 검토했다. 새 정확 채택과 독립 제어 시험/입력 동결 전 호출하지 않는다. LLM 청킹과 답변 생성·사용자 문서 선택은 여전히 독립적으로 남아 있다.

S1이 완료되어도 P032 전체나 최종 goal을 완료로 처리하지 않는다. 작은 모델만 통과한 경우 BGE 비교의 실패/미실행도 별도로 남긴다. 실제 SDK의 CPU worker는 현재 timeout 회수와 종료 시 RSS를 제공하지만 실행 중 pressure 감시를 제공하지 않으므로, S1 계약에는 해당 관찰·중단 경로의 구현 및 독립 검증을 포함해야 한다. P031의 준비용 monitor가 추론 worker에도 적용된다고 가정하거나 P013 recovery runner를 재사용하지 않는다.

[S1 실행 계약](P032-s1-execution-contract.md)에 다운로드·추론 작업 수, 시간·디스크·RSS 한도와 취소/회수 검증을 확정했다. P031 완료 검토 후 S1만 READY로 인계하며 S2/S3의 대기 사항은 유지한다. 위의 후보 설명보다 이 실행 계약을 우선한다.

P031 최종 도구/설치 artifact 검토는 완료했다. S1에서 generic parser의 새 source 구간과 승인 참고 자료의 매핑을 검토하고 실제 검색·리랭킹 결과를 확보한다. 선택 LLM·사용자 문서 입력은 S2/S3 준비 때 연결한다. plan은 실제 요청·다운로드·모델 실행을 수행하지 않았으며 dev 정확 채택 이후 S1 계약 범위로 시작한다.

[비교 행렬 초안](P032-comparison-matrix-draft.md)에 검색5행·리랭커3행·생성2profile·청킹5방식의 통제 조건과 업무 수를 구체화했다. 단일 축 실험이며 기존 결과 재사용과 실제 새 요청 수를 구분한다. 실제 선택 profile·전체 deadline·누적 상한·모니터링과 사용자 입력은 READY 전에 확정한다.
