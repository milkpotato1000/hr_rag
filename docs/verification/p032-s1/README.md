# P032 S1 — 공개 검색 모델 검증 기록

현재 단계: E5 실제 검색을 완료했으며 mMiniLM 첫 smoke의 `model_weights_mismatch`로 중단했다. P032 전체 완료가 아니다.

[비교 보고서](report-final/report.html)와 [실제 사례 학습 안내](../../learning/rag-package/live-retrieval-s1.md)에서 결과를 읽는다. BM25/E5 Dense/E5 Hybrid 검색 각 10건과 저장 후보의 모델 없는 none 재생 10건을 보존했다. 필수 사실 회수는 BM25 24/38, E5 Dense와 Hybrid 27/38이다. 답변 생성과 의미 평가는 수행하지 않았다.

## 중단과 보존

[ledger](run001/ledger.json)의 inference worker 25회 중 24회 성공, mMiniLM 1회 실패다. 준비 다운로드는 E5와 mMiniLM 각각 1회다. 시작한 worker의 종료를 확인했다. 실패한 20pair의 계산 완료 수는 미확정(null)이다. [진단](run001/mmini-failure-diagnosis.json)은 checkpoint의 I64 [1,514] position_ids와 locked SDK의 nonpersistent buffer 차이를 기록한다. 다른 mismatch의 전체 목록은 아직 측정하지 않았다. [검토 요청](../../feedback/dev/requests/R20261127-94452f98.json)을 별도 커밋 `dfc3e18`로 남겼다. BGE 두 모델은 미준비·미실행이다.

E5 준비 후 출력 디렉터리 누락으로 멈춘 첫 실패와 [복구 이벤트](run001/resume001-event.json)도 보존했다. 같은 started_at와 예산을 사용했고 재다운로드하지 않았다. [none 재생](run001/none-replay.json)과 [보고서 재생](report-final/replay-check.json)은 모델/네트워크 진입을 금지하고 기존 결과를 읽었다. ledger는 바꾸지 않았다. 후속 정확 READY의 별도 누적 실행 계약 없이는 재호출하지 않는다.

## 최종 설치와 화면

[최신 설치 identity](final-install-current/installation.json), [core-only](final-install-current/final-core-only.json), [sdist 재빌드](final-install-current/final-sdist-replay.json)를 확인했다. 실제 실행 wheel의 Python/lock과 최신 설치물의 동일성은 [payload 비교](payload-equivalence.json)에 있다. UI 안내는 검색 지표와 답변 품질을 구분한다. [패키지 회귀](regression-final.log) 134개가 통과했다.

설치 UI와 저장 결과 보고서를 소유 loopback에서 확인했다. 390px의 줄바꿈·원문 페이지/offset, Enter/Space 상세 열기/닫기와 Tab 이동을 확인했다. 모델 실행 권한은 모두 껐고 확인 후 소유 서버를 종료했다. [화면](report-current-desktop.jpg), [좁은 원문](ui-current-source-narrow.jpg), [검증 요약](final-checks.json)을 남겼다. 파일 선택창은 사용하지 않았으며 P029 C4 차단은 유지한다.

최종 core-only 설치 첫 시도는 sandbox의 기본 uv cache 접근 제한으로 실패했다. [실패](install-current-attempt001.log)를 보존하고 writable 임시 cache로 [재검증](install-current.log)했다. 모델 호출과 무관한 설치 검사다.

정확 채택은 `3f727c9ce0cd59fdac1337b7bf25acca8bb87c0a`, 채택 커밋은 `57afafb`이다. 생성·LLM 청킹·Drive·평가기·Ollama 제어·P013 grant는 실행하지 않는다. P013/P014 보류와 P029 C4 차단을 유지한다.

## 실행 전 검증

- [worker 독립 시험](owned-run002.log): 9개. 큰 pipe, timeout, pressure/RSS, 계측 실패, 취소, 지연 I/O 오류, 원래 오류와 진단 저장 실패의 분리를 확인했다.
- [패키지 회귀](regression-run002.log): 134개 PASS. [하네스](harness-run001.log): 35개 PASS.
- [실험 제어 독립 시험](control-run001.log): 4개 PASS. 2시간 deadline의 재시작 후 유지, dispatch 전 누적 예약, 실패 후 차단, pair 한도, 재다운로드 차단을 확인했다.
- [설치 identity](installation.json), [tiny SDK 결과](tiny-installed.json): source 없는 cwd의 wheel, core-only, sdist 재빌드, 실제 random tiny 네 역할. 실제 사전학습 품질 증거가 아니다.
- [보존 검사](preservation.json): 기존 1,513개 원문·평가·잠금 파일 hash 일치.

설치 검증 첫 시도는 시스템 Python 3.9의 `tarfile.extractall(filter=...)` 미지원으로 실패했다. [실패](install-verify-run001.log)를 남기고 프로젝트 Python 3.12로 [재검증](install-verify-run002.log)했다. 첫 wheel과 최신 수정 wheel의 identity도 각각 보존한다. 최초 source snapshot은 저장소 cwd에서 파싱했고, 권위 있는 `snapshot-installed`는 source 없는 설치 환경에서 별도로 파싱하여 identity 일치를 확인했다.

## 검색 결과를 보기 전 고정한 평가 자료

[최종 원문 검토](input/source-review-final.json), [고정 입력](input/frozen-inputs.json), [사실](input/facts.json), [전체 qrels](input/qrels.json), [청크별 사유](input/qrels-audit.json)를 사용한다. 합성 PDF 23쪽 전체를 읽었으며 201개 고정 청크 × 10개 질문 = 2,010개 관련성 판정을 기록했다. 필수 38개와 보충 19개는 승인 GT와 일치한다. 기존 원문의 offset을 복사하지 않고 새 추출문에서 문자열을 찾아 정확한 Unicode 구간을 저장했다.

최초 매핑은 [이전 시도](input/mapping-attempt001/source-review-final.json)에 보존했다. 최종 매핑에서는 독립 사실의 최소 주어·조건·서술 구간을 AND spans로 나누었다. 절차상 증빙 사용 금지를 정책 전체의 동치인 OR 근거로 쓰지 않는다. 이 절차 설명은 관련성의 부분 근거로만 남긴다. 단독 문장 끝 조각인 청크 85/149/171의 해당 질문 판정은 0이다. 이 수정은 어떤 검색 결과도 보기 전에 이루어졌다.

작성과 검토는 같은 Codex dev이며 독립 평가자 검증이 아니다. 사람의 기존 GT 승인과 새 source mapping 검토를 구분한다. 공개된 합성 질문의 결과는 일반적인 한국어 검색 성능을 보장하지 않는다. PDF 머리말·꼬리말이 원문에 남아 있으며 이번 고정 조건에서 제거하지 않는다. gt09/gt10의 검색 지표와 필수 사실 회수는 N/A이며 답변 보류 정확성을 평가하지 않는다.

## 실제 실행 경계

[고정 manifest](run001/manifest.json)와 [ledger](run001/ledger.json)를 사용한다. 최초 공개 모델 준비 때 `started_at=1795801676.159772`로 2시간을 시작했으며, 실패·미확정 후 자동 재시도나 한도 초기화를 하지 않는다. 파일 준비는 E5 → mMiniLM → BGE-M3 → BGE reranker 순서이며 각 모델은 smoke를 통과해야 전체 실행으로 진행한다. owned inference worker는 CPU float32/batch1/512tokens, 300초/4GiB/OS normal 조건으로 감시한다. 샘플 사이 순간 peak나 시스템 전체 OOM 방지를 보장하지 않는다.

실행 스크립트는 [live_run.py](live_run.py)이며 설치 기록의 Python을 source 없는 cwd에서 `PYTHONPATH` 없이 사용한다. `setup`은 이미 수행한 오프라인 고정 단계다. 이후 `prepare <모델>`, `smoke <모델>`, `search <embedding 또는 bm25>`, `rank <none 또는 reranker>`는 각각 명시 실행하며, 이 문서 열람이나 재생이 실제 작업 재실행을 뜻하지 않는다. 모델 파일과 캐시는 `.rag-runs/p032-s1-live/run001`에만 보존하며 Git에 포함하지 않는다.
