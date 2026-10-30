# P019 준비 검토 — 평가기 준비와 사람 승인 분리

2026-10-30 준비 완료. 사용자는 작업들을 연속 진행하도록 요청했다. 기존 P013은 모델/실제 승인 정답 없이는 READY가 될 수 없으므로, 그 게이트를 낮추지 않고 모델 실행 준비·미승인 정답 패킷을 P019로 분리한다. P018 완료 후 별도 dev에서 구현한다.

## 근거

- 로컬 Ollama GET version/tags/ps만 읽었다:0.40.8, qwen3:4b와 bge-m3:567m만 설치됨, ps 빈 목록. 읽기 sandbox 거부 후 승인된 읽기 권한으로 확인했으며 모델 생성/다운로드는 plan에서 하지 않았다.
- 총 메모리16GiB, 확인 시 작업 디스크 약333GB 여유. 이는 8B 실행 성공이나 실제 peak 보장이 아니다. dev는 실행 직전 여유/경합과 실제 memory 측정 범위를 확인한다.
- [공식 Ollama8B](https://ollama.com/library/qwen3:8b): Q4_K_M 약5.2GB/Apache-2.0. 공식 registry manifest bytes SHA를 직접 계산해 `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`와 model layer/size를 고정했다. [Qwen 모델 카드](https://huggingface.co/Qwen/Qwen3-8B)와 [Ollama schema 문서](https://docs.ollama.com/capabilities/structured-outputs)는 역할/형식 참고이며 로컬 실행 증거를 대신하지 않는다.
- 고정 입력 JSON은 P007 완료 commit의 source-v4 section map과 canonical을 직접 읽고 모든 extent quote/offset을 대조해 작성했다. 검색 qrels/결과를 모델 정답 입력으로 복사하지 않는다. 질문8개 원문 + 금액 미명시 후보2개다. 실제답변/claim은 아직 생성하지 않았다.
- P007 인계는 baseline fixed400/80과 후보 structure0, 원문 hash/실험 manifest/색인 fingerprint를 제공한다. 후속 선택을 임의 재수행하지 않는다. P017 사용자 설정 결과는 공식 평가 기준에 섞지 않는다.

## 범위·실패 경계

입력 안전성 검사는 8B 실제 metadata를 먼저 검증하고 매 호출 적용한다. tag 변경·입력상한 초과·다운로드/메모리/timeout 실패는 기록 후 plan에 돌아오며 자동확대/4B대체/근거삭제하지 않는다. 최대34회,timeout120초,45분wall과6GiB다운로드 상한은 준비 실험을 제한한다. P019 완료에는 사람 승인이 요구되지 않지만 P013의 실제 평가에는 여전히 필요하다.

P019의 작은 JSON/읽기 보고서는 검토 자료이며 P008 통합UI를 앞당기지 않는다. P013 기존 C1~C4는 보존하고 선행에 P019를 연결한다. P019 문서/fixture 검토만으로 실제모델 PASS를 보고하지 않는다. 기존 미커밋 네 문서는 보존한다.
