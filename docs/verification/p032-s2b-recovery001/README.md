# P032 S2b 환경 복구001

정확 READY f32ab2582d517301b55e3dfcc4676cf945c55d5d를579b06a에 채택했다. 기존 실패 환경과 p032-s2b 전체259파일은 preservation.json으로 고정한다. 같은 wheel9342add...와 retrieval lock f7988bdf...를 새 비공개 workspace venv에 한 번 설치했다. pip --retries0/require-hashes/only-binary와 준비900초/원래deadline을 적용했다. 제품 알고리즘·SDK 버전·모델 파일은 변경하지 않는다.

환경 감사는 lock45개 배포물의 존재/버전, RECORD의24,569개 hash, wheel의 제품파일, pip check, source-free CLI와 모델0 SDK import를 검사했다. 원격 wheel URL/hash는 pip-report.json 및 environment-audit.json에 남긴다. 생성 entrypoint/pyc/RECORD의 비hash 파일은 별도 목록이다. 실제 가중치나 모델 품질 통과를 의미하지 않는다.

초기 audit guard가 /token substring으로 stdlib tokenize.py를 오인한 실패를 audit-attempt001 및 environment-audit002.log에 보존한다. 두 번째 로그는 잘못된 cwd로 앞선 수정이 적용되지 않은 채 같은 모델0 감사를 수행한 기록이다. exact credential 이름/디렉터리와 weight 확장자 검사로 수정하고 독립 시험했다. plan도 같은 계약 내 검사 코드 수정임을 확인했다. 설치 재시도/모델 호출/900초 reset은 없다. preparation.json의 과거 halted는 보존하며 수정 후 결과는 environment-ready.json 및 environment-audit003.log다.

첫 freeze 검사도 원래 임시 경로용 source containment 조건이 workspace 내부의 새 설치 venv를 거부했다. 빈 준비 폴더와 검사본은 freeze-attempt001-run/ 및 freeze-attempt001.py/log에 보존했다. 설치된 sys.prefix/site-packages와 source 없는 cwd를 검사하도록 조정했고 freeze002.log가 PASS다. 실제 호출 전의 검사 코드 수정이며 기존 부모와 제품 코드는 불변이다.

control/runtime/live/freeze 및 test_control은 p032-s2b의 feea3c2 기반 파일에서 복사한 evidence runner다(정확 원본 feea3c24da28a0ee3a336356daac95eb2e4027c5). 실제 계산은 설치된 동일 wheel을 사용한다. child는 부모1worker/567requested/완료null을 보존하며 추가45worker/1896items와 누적46/2463을 예약 전에 검사한다. original start1795804963.61378/deadline1795808563.61378을 그대로 사용한다. 실패latch/두 질문gate/checkpoint/순차CPU/300초/4GiB/normal pressure/디스크2GiB 조건도 유지한다.

[독립 시험](tests-final.log)은 기존 제어18개와 환경/누적13개 PASS다. 실제 호출 전 원문·단위·모델·질문·설정·순서 동일성을 검증했다. config4개의 경로만 달라진 before/after를 run001/manifest.json에 기록한다. 초기 ledger는 아직 ready이고, 코드·입력·환경 증거를 커밋한 다음에만 실제 호출한다. S1/S2a/GT/P013/P014/P029 C4/grant는 그대로다. 전체 P032 완료를 뜻하지 않는다.


## 실제 완료 결과

동결 커밋 `e84c9a58568568c82eddb8d48e51ee5e66ec56e4` 이후 source 없는 cwd에서 새 설치 Python `-B -I`로 live.py를 한 번 실행했다. child semantic1 + index4 + query40 =45workers가 모두 성공했고 단일 compare CLI invocation의40행이 완성됐다. 추가1,579items 완료, 부모 실패567items 완료null을 포함한 누적46workers/2,146requested items다. 원래 종료1795808563.61378 전에1795806035.0906339에 완료했다. [원장](run001/ledger.json)과 [CLI 기록](run001/cli-compare.json)을 보존한다. 새 설치1회 외 다운로드·변환·모델교체·추가 smoke·자동재시도는 없다.

[학습 보고서](report.html)에서 branch union / 후보20 / top5 / 전달 문맥을 분리했다. 필수 fact38개 기준 fixed35/34/27/27, recursive35/34/29/29, structure35/31/29/29, semantic38/38/29/29다. gt09·gt10은 사실0으로 N/A이며 유효 분모8질문을 따로 표시한다. 새 qrels가 없어 chunk Recall/MRR/nDCG는 N/A이고 생성/평가도0이다. 모든 top5는2,000자 안에 들어 예산 제외0이다.

의미 청크250개는567단위에서 만들었다. 문서 마지막을 제외한249경계는 모두 maximum 이유이며 의미 threshold 단독 경계0이다. 원문 길이38,582자와 모든 overlap을 보존했다. 경계 모델 작업은10.42초, 관측 최대 RSS1,003,438,080bytes였다. 새 worker마다 모델 시작 비용이 포함되며 OS cache가 남을 수 있어 하드웨어 성능 일반화는 하지 않는다.

[독립 감사](report-check002.log)는40질문×3저장 단계=120개 fact 결과를 Unicode 위치 집합으로 검산하고, 별도 후보N20도 계산했다. 독립 RRF 순서·선택 문맥·문자 예산,566인접 벡터 거리·249경계·overlap을 확인했다. `chunk-report`/`chunk-replay` 설치 CLI도 source-free cwd에서 모델0으로 통과했다. 최초 model-free 보고서 검사는 load_build 인자를 빠뜨려 실패했으며 report-check001.log에 보존했다. 보고서 호출만 수정했고 실제 모델 재실행은 없다.

[화면 검증](browser-checks.json)은 실제 저장40행의 설치 UI·검색/전달/원문 페이지, 보고서1280/390폭·키보드 상세를 확인했다. [소유 서버 종료](ui-closed.json)와 금지 호출0을 기록했다. P029의 filepicker는 건드리지 않았다.

[최종 검사](final-checks.json)는 부모259파일, 기존 환경26,357파일, S1 3,521파일, S2a415파일, 보호1,513파일의 보존을 확인한다. frozen 입력/runner와 원장도 감사 전후 그대로다. 제품 알고리즘은 변경하지 않았으며 이전 실패를 없애지 않았다. S2b 비교 완료이며 전체 P032와 LLM 청킹·답변·Drive·평가기 완료는 아니다.
