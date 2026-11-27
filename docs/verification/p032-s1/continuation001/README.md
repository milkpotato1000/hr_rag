# P032 S1 legacy buffer continuation

정확 READY `b6b57a9e11ac68e55b0bb475343a4df4092b5586`, 채택 `4614e37`. 부모 run001의 halted ledger와 성공·실패 산출물은 변경하지 않는다. 고정 mMiniLM revision의 position_ids만 원본/재생성 buffer의 dtype·shape·arange 값을 검증한 뒤 persistent state 비교에서 별도로 처리한다. 나머지 키·shape·classifier 조건은 유지한다.

[실제 tiny SDK](legacy-sdk.json)는 무작위 작은 XLM-R로 15개 정상/변조 조건과 3개 소유 worker 경로(정상/legacy/변조)를 확인한다. 실제 사전학습 품질 시험이 아니다. [134개 회귀](regression.log), [35개 하네스](harness.log), [누적 실행 제어 6개](control-final.log), [새 설치물](install/installation.json), [core-only/sdist](install/final-sdist-replay.json), [1513파일 보존](preservation.json)을 대조한다.

최초 sandbox 실행은 SDK 설치의 DNS, loopback 회귀의 포트 접근, tiny 시험의 OS 계측 제한으로 실패했다. attempt001 로그를 각각 보존하고 승인된 격리 설치/소유 loopback/소유 worker 계측 범위로 재검증했다. 모델 실험의 실패나 예산을 재시도한 것이 아니다.

별도 run ledger는 최초 시작 `1795801676.159772`와 deadline `1795808876.159772`, 기존 inference25회/실패20pairs를 계승한다. 누적 상한은73workers/500pairs, 새 호출 최대48workers이며 E5 재실행·E5/mMiniLM 재다운로드는 금지한다. 실패 시 다음 모델로 진행하지 않는다. S2/S3·평가기·LLM·API·Drive·Ollama·P013 grant·P029 C4 경계는 유지한다.
