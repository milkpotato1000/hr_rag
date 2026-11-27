# P032 S1 legacy buffer continuation

정확 READY `b6b57a9e11ac68e55b0bb475343a4df4092b5586`, 채택 `4614e37`. 부모 run001의 halted ledger와 성공·실패 산출물은 변경하지 않는다. 고정 mMiniLM revision의 position_ids만 원본/재생성 buffer의 dtype·shape·arange 값을 검증한 뒤 persistent state 비교에서 별도로 처리한다. 나머지 키·shape·classifier 조건은 유지한다.

[실제 tiny SDK](legacy-sdk.json)는 무작위 작은 XLM-R로 15개 정상/변조 조건과 3개 소유 worker 경로(정상/legacy/변조)를 확인한다. 실제 사전학습 품질 시험이 아니다. [134개 회귀](regression.log), [35개 하네스](harness.log), [누적 실행 제어 6개](control-final.log), [새 설치물](install/installation.json), [core-only/sdist](install/final-sdist-replay.json), [1513파일 보존](preservation.json)을 대조한다.

최초 sandbox 실행은 SDK 설치의 DNS, loopback 회귀의 포트 접근, tiny 시험의 OS 계측 제한으로 실패했다. attempt001 로그를 각각 보존하고 승인된 격리 설치/소유 loopback/소유 worker 계측 범위로 재검증했다. 모델 실험의 실패나 예산을 재시도한 것이 아니다.

별도 run ledger는 최초 시작 `1795801676.159772`와 deadline `1795808876.159772`, 기존 inference25회/실패20pairs를 계승한다. 누적 상한은73workers/500pairs, 새 호출 최대48workers이며 E5 재실행·E5/mMiniLM 재다운로드는 금지한다. 실패 시 다음 모델로 진행하지 않는다. S2/S3·평가기·LLM·API·Drive·Ollama·P013 grant·P029 C4 경계는 유지한다.


## 실제 완료 결과

[최종 비교 보고서](report-final/report.html)의 80개 행을 확인했다. 검색 5설정×10질문=50건, 고정 E5 Hybrid 후보의 none/mMiniLM/BGE 리랭커 3설정×10질문=30건이다. [감사](final-checks.json)는 부모 1,304파일 hash·기존 job prefix·원래 시작과 deadline·1513 보호 자료를 검산했다. 80개 문맥의 fact 회수도 패키지 함수를 쓰지 않고 Unicode 위치 집합 포함관계로 대조했다.

최초 실패를 포함한 inference는 73회 예약/시작, 72회 완료·1회 실패다. reranker 요청은 500pairs, 확인된 완료는 480pairs다. 실패 1작업의 요청 20pairs는 실제 완료량 null을 그대로 유지한다. 준비 worker는 다운로드4와 변환1이다. 시작한 worker를 모두 회수했고 원래 deadline 안에 종료했다. 실제 LLM·평가기·API·Drive·Ollama 제어와 P013 grant는 0이다.

mMiniLM은 정확 위치 buffer를 검증한 뒤 stored202/loaded201, 그 외 diff0을 확인했다. BGE reranker는 예외 없이393/393이 일치했다. BGE-M3 최초 tensor-only 변환의 관측 RSS는2478555136bytes였다. 이는 이 CPU 환경과 입력의 표본 관측이며 순간 peak나 다른 환경 전체의 안전을 보장하지 않는다.

같은 후보에서 필수 사실 회수는 none27/38→mMiniLM28/38→BGE30/38이다. nDCG는0.773→0.746→0.784다. mMiniLM gt03은3/8→5/8, gt04는2/2→1/2이며 BGE gt03은3/8→8/8, gt06은3/3→1/3이다. 집계 개선과 개별 질문 퇴행을 함께 기록한다. 답변 평가 값은 null, 근거 없는 두 질문의 지표는 N/A다.

[설치 UI/보고서 관찰](browser-checks.json)에는 실제 저장 결과, 모델 실행 비활성, desktop/390px·원문 위치·키보드 동작과 소유 서버 종료를 남겼다. 파일 선택창은 시도하지 않았다. 준비 profile의 미검증 표시는 자동으로 품질 통과로 바꾸지 않았으며, 별도 보고서가 이번 한정 실험의 관찰 범위다. 브라우저 viewport가 처음에는 UI 탭에만 적용돼 보고서가1280px였던 관찰은 desktop 파일로 보존하고, 보고서도 실제390px로 표시한 화면을 따로 확인했다.

이 작업은 S1 범위 완료다. P032 전체·생성/LLM 청킹·사용자 Drive와 평가기는 미완료/보류다. 원래 모델 작업 예산을 모두 사용했으므로 새 실행 계약 없이 추가 실제 호출하지 않는다. 원본 추출 텍스트와 인용 HTML의 줄 끝 공백은 hash·원문 보존을 위해 유지했으며, 소스/수기 안내의 whitespace와 문서 링크는 별도 점검했다.
