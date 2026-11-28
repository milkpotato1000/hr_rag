# P032 S2d — 로컬 4B 첫 답변 중단

**실제 생성 1회 후 중단했습니다.** gt01 생일휴가 질문에서 출력 상한1,024토큰에 도달해 `truncated`/`finish_reason=length`를 반환했습니다. 제품은 `provider_truncated`로 거부했고 유효 답변은0개입니다. gt02~gt10은 미실행이며 재시도·조건 변경·자동 확대는 하지 않았습니다.

[읽기용 보고서](report.html) · [결과 요약](results.json) · [실제 제품 결과](answers/gt01/result.json) · [Codex 원문 대조](answer-review.json)

## 실제 관측

- 사용자 선택: 기존 로컬 `qwen3:4b`, 현재 규정집. Drive는 명시 보류.
- READY `876067dc2f383fdc806d9e6f70031360e05c2c4d`, 채택 `d19393e`, 제어/입력 동결 `8b43cd520c4f65c54785be4961d678e6da5e7dd8`, 현재 identity·사전 관측 커밋 `d5b88d8024377cf48fc59b84897a66b0b14bf0c0`.
- S2c 설치 wheel `87744fba87853c84a2a3c9b05b80a727c72d1113812139029210f4d664fba6bd`의 실제 core-only CLI `answer-from-rerank`를 사용했습니다. fake response나 직접 요청 우회로 생성하지 않았습니다.
- 과거 digest와 현재 전후 digest 일치. Ollama0.40.8, Qwen3-4B-Thinking-2507 계열·Q4_K_M. `/show`의 model_info도 Thinking/2507을 보고합니다. HF 원본 출처는 역사 기록이며 서버가 원격 HF revision을 검증한 것은 아닙니다.
- 입력1,778토큰·출력1,024토큰, provider 처리87.417초·adapter 전체87.473초. HTTP 응답은 도착했으나 정상 종료 답변은 아닙니다. JSON 업무 schema·인용 검토 전 잘린 응답으로 차단됐습니다.
- 합산 RSS 표본 최고3,950,428,160bytes(약3.68GiB), 모든 관측 pressure normal. 이 값은 시스템 전체/GPU 순간 peak나 다른 환경의 메모리 보장이 아닙니다.
- `keep_alive=0` 이후 `/ps` 적재0과 normal30초 복귀 확인. 소유 client 회수 및 이번 작업 소유 Ollama 종료. 다른 프로세스·기존 서버 강제 종료 없음. 로컬 lock과 /ps 관측은 외부 클라이언트 부재를 완벽하게 보장하지 않습니다.
- metadata30회: version1/tags3/show1/ps25. 생성1회, 검색·임베딩·리랭커 재실행0, 새 다운로드·API·Drive·평가기0, 기존 P013 grant 미소비.

## 해석

gt01 전달 문맥에는 승인된 필수 근거6/6이 있습니다. 이번 실패를 검색 누락이나 필수 정보 생략으로 판정하지 않습니다. 완성된 답변을 얻지 못했으므로 답변의 정확성·충실성·인용 의미 지지는 평가 불가입니다. 1,024토큰을 왜 모두 사용했는지(장황함·반복·thinking 등)는 저장된 정규화 결과만으로 단정할 수 없습니다. 미완성 raw 본문이나 hidden thinking을 복원·가공해 성공으로 만들지 않았습니다.

기존 ledger는 최초 오류와 보수적인 `server_completion=unknown`을 보존합니다. 별도 관측은 HTTP 응답 수신·모델 해제·normal 복귀를 확인합니다. 이를 강제 취소 성공으로 바꾸지 않습니다. 질문별 reserve는 사용한 시도로 남고45분 deadline을 초기화하지 않습니다. 원본 gt03=3/8·gt08=2/8 근거 회수 부족과 gt09/10의 fact0/N/A도 보고서에 보존하지만 실제 답변 결과는 없습니다.

## 준비·검증 근거

[동결 입력/profile/scripts](frozen.json), [10개 모델 없는 preview 명령](preview-commands.json), [독립18개 제어 시험](tests003.log), [현재 모델 관측](identity-observed.json), [실행 ledger](ledger.json), [정리 관측](gt01-observation.json), [서버 종료](server-closed.json), [자원 표본](resources.jsonl), [보존 hash](preservation.json), [최종 검사](final-checks.json).

설치 payload bytes와590입력파일+PDF를 대조하고 요청별 messages/actual_messages/body fingerprint를 동결했습니다. GT/facts/qrels는 모델 입력에 넣지 않았습니다. 전용 runner가 기존 real HTTP transport의 앞뒤에 요청 예약/기록을 붙였고, metadata에5초·200회 cap을 적용했습니다. product adapter·parser·prompt·모델 기본값은 변경하지 않았습니다.

제어 시험은 중복·병렬·순서·10회/45분/metadata 상한·identity·pressure/RSS·watchdog·미확정 후 dispatch 금지·소유 client 회수를 모델 없이 확인했습니다. 최초 가짜 process fixture가 terminate 뒤에도 오래된 poll 값을 반환한 시험 실패를 tests002.log에 보존하고 fixture만 수정해18개 PASS를 얻은 뒤 실제 실행했습니다. 초기 compile 명령의 시스템 cache 쓰기 차단은 AST 검사로 처리했습니다.

보고서는 질문→동결 문맥→실제 답변/실패→원문 대조→접힌 실행 상세 순서입니다. [데스크톱](report-desktop.jpg)과 [390px 화면](report-narrow.jpg), Enter/Space·Tab 관찰을 [화면 검증](browser-checks.json)에 기록했습니다. 기존 파일 선택창 제약을 재시도하거나 우회하지 않았습니다. 소유 보고서 서버도 검증 후 종료합니다.

출력 상한/응답 길이 정책의 다음 실험은 별도 plan 검토·정확 READY가 필요합니다. 이 중단을4B 품질 통과나10문항 완료로 표시하지 않습니다. Drive·LLM 청킹·API·P013/P014·P029 C4 상태는 유지하고 전체 P032도 미완료입니다.
