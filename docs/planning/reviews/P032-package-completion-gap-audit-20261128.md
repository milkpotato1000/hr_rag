# P032 패키지 전체 목표의 남은 검증

## S18 종료 후 전체 요구 대조

검토 기준은 공개 dev 커밋 `2aeee85`이다. 아래 행은 해당 버전의 설치본·실행 기록을 가리킨다. 뒤의 초기 감사와 당시 대기 상태는 이력으로 보존한다.

| 요구 | 확인 범위 및 남은 검증 | 근거 |
| --- | --- | --- |
| 설치 및 학습 | 새 가상환경의 wheel에서 기본 PDF와 CLI·UI를 검증했다. Codex·Claude Code용 실습 요청이 있다. 두 제품에서 각각 새로 설치해 끝까지 실행한 증거와 다른 OS 검증은 남아 있다. | [첫 설치](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/verification/p032-s10/README.md) · [도구별 요청](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/rag_package/resources/sample/START_HERE.md) |
| 문서 연결 | 로컬 PDF를 지정한 설치본에서 해당 파일의 고유 근거를 BM25 1위·1쪽으로 확인했다. Drive 단일 링크는 모의 인증·HTTP 검증까지이며 실계정 연결은 사용자 보류다. 브라우저 파일 선택창은 별도 미검증 경로다. | [내 파일](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/verification/p032-s16/README.md) · [Drive](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/learning/rag-package/drive.md) · [선택창](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/verification/p029/README.md) |
| 모델 선택·비교 | 같은 문맥에서 로컬 4B 실답변과 API 미리보기를 비교했다. 설치본에서 로컬·OpenAI·Anthropic 설정이 가능하다. 두 실제 생성 모델의 품질 비교와 실계정 API 응답은 미측정이다. | [생성 비교](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/verification/p032-s5/README.md) · [모델 설정](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/verification/p032-s14/README.md) |
| 청킹 | 고정·재귀·구조·의미 청킹의 검색 비교와 고정·재귀 청킹의 실답변 비교가 있다. 현재 4B의 LLM 청킹은 후보 ID 제한 후에도 출력 상한에 도달했다. 해당 실행에서 만들어진 청크나 검색 결과는 없다. | [네 방식](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/verification/p032-s2b-recovery001/README.md) · [실답변](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/verification/p032-s13/README.md) · [LLM 청킹](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/verification/p032-s18/README.md) |
| 검색·리랭커 | BM25, E5/BGE Dense·Hybrid와 고정 후보 리랭킹을 실측했다. 검색 10문항 중 관련 근거가 있는 8문항을 검색 지표 평균에 사용했다. 설치본에서 임베딩·리랭커만 바꾸는 구성도 확인했다. | [방법별 측정](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/learning/rag-package/live-retrieval-s1.md) · [선택 경로](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/verification/p032-s15/README.md) |
| 답변과 인용 | 단일 질문의 기한·승인권자는 실제 4B 답변·인용과 PDF를 대조했다. 복합 gt01의 S2h 실행은 잘렸다. 단순 질문 성공으로 복합 질문의 필수 사실 회수나 근거 없는 금액 질문의 적절한 보류를 판정할 수 없다. | [기한](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/verification/p032-s8/README.md) · [승인권자](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/verification/p032-s11/README.md) · [복합 질문](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/verification/p032-s2h/gt01-review.json) |
| 자동 평가기 | 사람 승인 정답지와 판정 기대값은 확보했다. P013/P014 평가기·NLI 실험은 보류 중이며 검색 지표와 답변 개별 대조를 자동 평가 점수로 사용하지 않는다. | [검토 기준](https://github.com/milkpotato1000/hr_rag/blob/2aeee8595b4b131b1ae1da649e3feafa8588fa0e/docs/planning/reviews/P013-human-review.md) |

다음 로컬 답변 검증 후보는 승인된 gt09 “재택근무 전기요금의 월 지원 한도는 얼마인가요?”다. 실제 전달 청크, 금액·미지급 단정 여부, 근거 부족 안내, 응답 상태를 각각 대조해야 한다. 검토 문서의 우선순위이며 이 기록만으로 모델을 호출하지 않는다. Drive·평가기 보류와 S18 단일 호출 종료를 유지한다.

2026-11-28 plan 읽기 전용 감사. dev의 S1 완료 `3ce2ed8c95f9259f1184c67e52373c7411e331b5`, S2a 완료 `17ea6305bb483409b9cd593d62e2e64c50c10625`, S2b 정확 채택 `192b948099567cbb852f200417fc30f4f3da27ef`를 구분한다. S2b는 진행 중이며 실제 실행 성공을 이 문서에서 추정하지 않는다. 이 검토는 새 실행 승인이나 제품 문서 수정이 아니다.

최종 목표는 문서 링크부터 모델·청킹·검색·리랭커 비교와 최종 답변까지 이어지는 설치형 학습 패키지다. 실제 검색 비교 성공이나 모델 없는 preview만으로 이 전체 목표를 완료할 수 없다.

## 후속 관찰: S2b 완료와 S2c 진행

2026-11-28 후속 읽기 전용 확인. 아래 초기 감사의 “S2b 진행 중”은 작성 당시 상태다. 현재 S2b recovery001 실제4방식×10질문은 완료됐으며 증거 `7fb8705c7de82b58acabed0e6212e2c85cc2ca3d`, 완료 기록 `93e2ea593da21ec2620b0dc583b3ce57454cc172`, 최종 안내 `af524c65f31504e85e390677784417f5a7cb6186`가 personal/dev에 전달됐다. [40검색 독립 검산](P032-s2b-search-results-audit-20261128.md)과 [의미 경계 대조](P032-s2b-semantic-boundary-audit-20261128.md)를 근거로 청킹별 검색 비교의 미완료 항목 중 규칙3종·의미 방식만 해소했다. LLM 방식·청킹별 실제 답변은 여전히 남는다.

학습 시작점 혼동은 [S2c 계약](../specs/P032-s2c-learning-entry-contract.md)의 READY `9be41de90ec370d67db4e2af4bf70e5636d5c2bf`로 넘겼다. 기존 dev의 수신 설명과 정확 채택 commit `c12b2e2`를 직접 확인했으며, 해당 호스트 작업은 진행 중이다. 이 관찰은 문서 수정·새 설치 검증의 완료를 뜻하지 않는다. 완료 후 실제 학습 첫 경로와 source 없는 새 설치 증거를 대조한다.

남은 목표는 실제 선택 생성 profile·LLM 청킹과 답변 비교, 실제 지정 문서 저장소 연결, 일반 학습자의 재현 가능한 설치·실행 경로다. P029 C4의 화면 증거도 남는다. 이미 질문한 생성 경로와 Drive 문서의 사용자 선택을 기다리며, S2c 문서 작업이나 기다린 시간을 실제 모델·계정 실행 승인으로 해석하지 않는다. 평가기 실험 보류는 유지한다.

## 요구별 증거와 남은 부분

| 요구 | 확인한 증거 | 아직 필요한 검증 |
| --- | --- | --- |
| 공개 모델 기본, 상용 LLM API 선택 | P025 adapter, P031 model preparation, S1의 E5/BGE와 두 reranker 실제 CPU 실행 | 범용 패키지의 실제 답변 생성과 선택 profile 비교. API의 fake/loopback 시험을 유료 API 성공으로 확대하지 않음 |
| 청킹 선택과 비교 | P030 구현, S2a 규칙3종 실제 경계·semantic/LLM preview, S2b 정확 채택 | S2b 실제4방식 결과와 별도 선택된 LLM의 실제 경계·검색·답변 연결. 저장 replay와 LLM 재호출 변동성 검증 구분 |
| Dense/Sparse/Hybrid와 임베딩 비교 | P010 구현, S1 BM25/E5/BGE 50검색 결과 | 새 청킹 artifact의 검색 결과와 비용·근거 회수 비교. S2b는 새 chunk qrels가 없어 순위 지표 N/A이며 source fact coverage 사용 |
| 리랭커 on/off와 모델 비교 | P020 구현, S1 none/mMiniLM/BGE 30결과, 동일 후보 통제 | 저장 결과를 사용자가 설치 CLI/UI에서 찾아 비교하는 전체 안내의 일관성. 검색이 개선되어도 답변 품질 개선을 자동 추정하지 않음 |
| 사용자 문서 링크 | P027 Google Drive 단일 파일 REST/OAuth 코드와 fake 인증·HTTP 검증 | 지정된 실제 테스트 문서·사용자 인증 후 수집→snapshot→검색→답변. 임의 웹하드 전체 지원을 주장하지 않고 지원 connector와 미지원 링크를 명시 |
| 최종 답변 | 기존 Naive/LangChain 이력과 범용 provider/ask 오프라인 검증 | 현재 독립 설치물에서 선택 profile의 실제 답변·인용·근거 부족 시 보류와 실패 검토. 기존 다른 경로의 성공을 그대로 승계하지 않음 |
| Codex 또는 Claude Code 실습 | P028/P031 독립 venv·source 없는 cwd, 두 도구용 요청 예시 | 실제 제공 파일·명령만으로 새 학습자가 경로를 따라갈 수 있는 재현 기록. 예시 프롬프트 존재를 양쪽 제품 UI 실사용 검증으로 표시하지 않음 |
| 학습 UI | P029 부분 화면 검증 및 후속 S1/S2a 허용 loopback 관찰 | P029 C4의 native 파일 선택/업로드 관찰은 여전히 미완료. 다른 관찰 성공이나 HTTP 시험으로 대체 완료하지 않음 |

P013/P014 평가 실험은 계속 보류한다. 위의 원문·사실 구간 산술 대조와 답변 수동 검토는 자동 LLM/NLI 평가기 실행 성공을 뜻하지 않는다. main 승격·PyPI 게시도 dev 전달과 별도이며 명시 요청 없이 수행하지 않는다.

## 학습 문서에서 발견한 상태 혼동

확인 대상은 dev의 `docs/learning/rag-package/`다. plan에서 제품 안내를 직접 고치지 않으며, 후속 dev 문서 정리 시 실제 완료 증거와 대조해야 한다.

- `ui.md` 첫 문단은 실모델 품질 미검증을 포괄적으로 표현한다. 현재 S1의 실제 검색·리랭커 결과와 설치 UI 저장 결과 관찰, 아직 미검증인 생성/API/개인 Drive를 구분할 필요가 있다.
- `models-and-support.md` 상단 역할 표는 S1 실제 실행을 반영했지만 하단의 “사전학습 가중치와 한국어 품질은 미검증” 문구 및 일부 기능 표는 이전 상태다. 작은 공개 학습 세트의 실제 관찰과 일반화 품질 미검증을 나누어 설명해야 한다.
- `install-current.md`는 S1 안내 링크를 추가했으나 “최신 검증 소스와 배포물 hash”를 P031로 안내한다. S1의 호환 수정 이후 실제 사용 wheel은 `9342add625a9ed633dffb2fccb3bad27379e8cddaf9a06836ea5a224fe9f280a`다. 설치 재현 기준은 기록의 source SHA·wheel·SDK가 서로 맞아야 하며 움직이는 dev HEAD와 고정 검증본을 구분해야 한다.
- `README.md`의 P024 설계 예시 JSON은 실행 불가라고 명시되어 있다. 이 경고 자체를 제거할 문제가 아니라, 신규 사용자가 실행 가능한 init/설정/설치 안내에 먼저 도달하는지 확인할 항목이다. 과거 예시와 현재 스키마를 섞지 않는다.
- `chunk-boundaries-s2a.md`의 모델0 상태는 S2a 기록으로서 맞다. S2b 완료 후 이를 소급 수정하지 않고 실제 비교 안내와 현재 상태 링크를 추가해야 한다. 실제 LLM34window는 여전히 preview다.

후속 정리 검증은 학습 시작점→설치 기준→설정→모델 준비→문서→청킹→검색/리랭커→실제 답변→저장 재생의 링크·명령·현재 상태가 일치하는지 확인한다. 기존 실패·미검증·지원 한계를 지우거나 실제 호출을 다시 수행하는 작업과 묶지 않는다.

## 다음 단계 경계

현재 dev는 [S2b 계약](../specs/P032-s2b-nonllm-chunking-contract.md) 범위만 진행한다. 이 감사의 문서 정리나 남은 실제 실행은 그 계약에 자동 추가되지 않는다. S2b 결과를 검토한 뒤 필요한 후속 계약에 반영한다. 생성 route와 Drive 링크에 대한 이미 제시한 사용자 질문은 답변 대기이며, 대기 시간이 경과했다고 선택된 것으로 간주하지 않는다.
