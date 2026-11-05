# Project B — P013 답변 평가기

승인된 가상 HR 정답과 고정 기대값으로 평가기를 검증하는 독립 모듈입니다. 실제 RAG 답변 품질과 평가기 자체의 정확도를 분리합니다. 현재는 오프라인 기반과 고정 추출/판정 실행 경로를 구현했으며 실제 S4 연결은 아직 활성화하지 않았습니다. P013 전체 완료 상태가 아닙니다.

## 실행 순서

1. 기존 run004와 원문을 보존하며 실제 승인 sidecar의 파일·패킷 hash를 대조합니다.
2. S1에서 schema·산식·인용·누락/중복·버전·오프라인 재생을 검증합니다.
3. S2에서 질문/고정 답변만 Qwen3:8b에 전달합니다. 숨긴 기대값/원문을 보내지 않습니다.
4. S2 전건 통과 후 S3 고정 근거 판정·전체 reference 매칭을 검증합니다.
5. S3 통과 후에만 S4 실제 Naive 실행을 연결합니다. 미통과/미확정이면 진행하지 않습니다.

```sh
python3 -B evaluation/project_b/freeze.py --out evaluation/project_b/artifacts/p013-run001
python3 -B evaluation/project_b/cli.py validate --manifest evaluation/project_b/artifacts/p013-run001/manifest.json
python3 -B evaluation/project_b/cli.py run --manifest evaluation/project_b/artifacts/p013-run001/manifest.json --stage extraction
python3 -B evaluation/project_b/cli.py replay --run-dir evaluation/project_b/artifacts/p013-run001 --output /tmp/p013-replay.json
python3 -B evaluation/project_b/cli.py report --run-dir evaluation/project_b/artifacts/p013-run001 --output /tmp/p013-review.html
python3 -B evaluation/project_b/cli.py export-bundle --run-dir evaluation/project_b/artifacts/p013-run001 --output /tmp/p013-bundle
```

run에는 정확한 manifest에 연결된 S1 검증 증거가 필요합니다. 생성한 실험의 입력·코드·프롬프트를 호출 후 변경할 수 없습니다. 새 실행 폴더로 카운터를 초기화하지 않습니다. 실행 실패/timeout도 원장에 남기고 자동 재시도하지 않습니다. 모델 없이 validate/replay/report/export-bundle을 실행할 수 있습니다. bundle에서는 `python3 -B code/cli.py replay --run-dir . --output replay.json`을 사용합니다.

## 학습할 지표

Faithfulness/Neutral/Contradiction은 실제 전달 문맥으로 E/T·U/T·C/T를 계산합니다. 판정 불능이 있으면 세 점수 모두 null이며, 0개 주장은 no_claims입니다. 핵심 Correctness는 필수 정답과 핵심 생성 사실의 일대일 매칭으로 TP/FP/FN·P/R/F1을 계산합니다. 참인 보충의 누락은 감점하지 않지만 거짓/미확정 보충을 숨기지 않습니다. 의도 충족률과 claim Recall은 별도입니다.

추출 단독 실험은 답변에 실제 쓰인 사실을 보존하는지 봅니다. 표현이 다르면 자동으로 틀렸다고 처리하지 않습니다. exact_diagnostic은 정확 문장·발생 위치 대조일 뿐이며 의미 판정이 필요한 결과의 최종 추출 P/R/F1은 null로 남습니다. 사람의 원문 검토는 버전과 인용이 연결된 sidecar로 소비합니다. 정답 전체를 이미 승인했어도 새 모델 출력까지 승인한 것으로 해석하지 않습니다.

## 현재 실행 결과

`artifacts/p013-run001/review.html`에 첫 추출 요청 결과를 보존했습니다. 두 기대 사실은
정확히 추출했지만 실행 중 OS 메모리 압력이 critical에 도달해 1/16회에서 중단했습니다.
S3/S4는 실행하지 않았으며 P013은 미완료입니다. `ledger.json`의 중지 상태를 지우거나
새 디렉터리로 예산을 초기화하지 마세요. 자원 중지의 검토·복구 방안은 별도 plan 검토 대상입니다.
