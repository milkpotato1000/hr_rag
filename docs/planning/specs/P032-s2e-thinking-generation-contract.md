# P032 S2e — 로컬 Thinking profile과 최종 답변 전용 검증

2026-11-28 READY. 사용자 기존 로컬 Qwen4B·규정집 실제 답변 목표 안에서 dev 접수 R20261128-d2a75c04를 처리한다. S2d는 첫 요청에서 truncated로 종료됐고 이후 호출은0이다. [준비 검토](../reviews/P032-s2e-readiness-20261128.md), [이전 중단 artifact hash](../reviews/p032-s2d-halt-audit.json)를 따른다. Drive·평가기·LLM 청킹·API·다른 모델은 계속 제외한다.

## 확인된 문제와 목적

현재 고정4B는 Qwen3-4B-Thinking-2507 계열이며 [Qwen 공식 카드](https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507)는 Thinking 전용과 temperature0.6을 설명한다. [Ollama thinking](https://docs.ollama.com/capabilities/thinking)은 message.thinking과 message.content 분리를, [chat API](https://docs.ollama.com/api/chat)는 think 선택과 format JSON을 설명한다. 확인일2026-11-28. 최신 문서가 설치된0.40.8의 모든 동작을 증명하지는 않으므로 실제 호환성은 이번 제한 시험에서 확인한다.

기존 제품은 think=false 고정, nonempty thinking을 무조건 거부한다. 이 정책은 기본 동작으로 보존하되 Thinking 전용 모델을 명시 선택한 profile에는 분리된 최종 content만 수용하는 경로가 필요하다. S2d의 출력1024/finish_reason=length만으로 토큰이 thinking에 쓰였다고 단정하지 않는다. 원문6/6 제공과 정상 자원, 잘린 응답은 관측 사실이며 정확한 원인은 미확정이다. 단순 token 상향 반복 대신 명시적 모델 모드 호환성을 갖추고 한 번 시험한다.

## 제품 변경 범위

1. Ollama profile/spec에 선택 `think` boolean만 추가한다. 미지정/false는 기존 false 동작·요청 fingerprint를 유지한다. true는 요청 body think=true로 전달한다. null/문자열/숫자는 거부하고 API provider에 이 필드를 넣으면 거부한다. schema1/2의 다른 역할·키·identity 검사는 그대로다.
2. configure/spec→validate→preview→invoke→answer-from-rerank와 기존 profile 복제/등록 경로에서 이 선택이 보존돼야 한다. 모델 이름을 보고 자동으로 true로 바꾸지 않는다. schema 전체 재설계나 API thinking 지원은 범위 밖이다.
3. 명시 true일 때에만 별도 message.thinking 문자열이 있어도 최종 message.content를 기존 strict 검증으로 넘긴다. thinking은 메모리에서 즉시 폐기하고 결과·로그·UI·본문·오류·원문 HTTP dump에 저장하지 않는다. thinking 본문 hash/발췌/재구성도 남기지 않는다. 요청 true/false 및 분리 필드 존재 여부 같은 boolean 관측만 허용한다. malformed thinking type은 실패로 처리한다.
4. content의 `<think>` 계열 태그, malformed JSON/중복 key/nonfinite, 빈 content, length/timeout/refusal/toolcall/identity 불일치와 업무 schema/인용 오류는 여전히 실패다. content에서 태그 사이를 삭제하거나 Markdown fence를 벗겨 복구하지 않는다. think=true는 최종 답변 검증 완화가 아니다. false/미지정의 예상하지 않은 thinking 거부는 유지한다.
5. Ollama usage.eval_count는 provider 전체 출력 토큰으로 표시한다. thinking/final별 정확한 토큰이 없으면 각각 미측정이며 content 길이로 토큰을 꾸며내지 않는다. 최종 검토 표에는 유효 answer만 넣고 reasoning trace는 노출하지 않는다.
6. 관련 학습 문서에는 기본 false와 명시 true의 의미, Thinking 전용 alias, 출력 예산과 최종 답변 길이의 차이, 실제 관측/미검증 범위를 설명한다. 설치용 sample 기본값과 기존 model digest/GT/prompt는 변경하지 않는다. 필요 문서만 고치고 새 모델 다운로드·모델 전환은 하지 않는다.

## 모델0 검증과 새 설치

명시 true+분리 thinking+유효 JSON은 final content만 성공해야 한다. 미지정/false의 nonempty thinking, true의 malformed thinking, content에 섞인 thinking 태그, thinking만 있고 빈content, 잘린 응답, malformed 업무 JSON, 위조 인용, API에 local-only think, bool 아닌 값, spec/preview/복제의 값 보존을 각각 검증한다. 합성 sentinel thinking 문자열이 전체 결과·로그·UI용 JSON 어디에도 남지 않는지 검사한다. 모든 fixture는 가짜 응답/소유 loopback만 사용한다.

관련 provider/config/setup/rerank-answer 및 UI profile 복제 회귀를 실행하고 payload/manifest·wheel/sdist를 갱신한다. 별도 core-only 설치/source 없는 cwd에서 CLI 설정과 실제 제품 함수 경로를 모델0으로 확인한다. old wheel87744fba와 S2d721파일, 이전 입력/GT/실패/runtime baseline은 보존한다. 기존 retrieval SDK와 모델 환경을 재설치하지 않는다. 모델0 준비·시험·source/profile/runner/입력/배포물 동결 커밋 전 실제 호출하지 않는다.

## 제한된 실제 확인: gt01 한 건

S2d와 동일4B digest `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`, 동일 gt01 저장 none rerank artifact·1280자 문맥·질문·제품 system prompt를 사용한다. 새 profile은 think=true, temperature=0.6, max_output_tokens=4096, num_ctx=8192, seed42, response_mode=json_object, HTTP480초, keep_alive0이다. top_p/top_k 등의 기존 미설정 옵션은 이번에 새로 추정하지 않으며 effective request와 서버 metadata를 기록한다. 공식 카드의 모든 권장값을 따른 완전한 benchmark라고 표현하지 않는다.

이것은 think/temp/출력예산을 함께 조정한 호환 설정 시험이며 단일 변수 인과 실험이 아니다. 4096은 이 기기의 제한 진단 예산으로, 모델 권장 최대치나 성공 보장이 아니다. 제품 content/인용/JSON 규칙과 질문/문맥은 유지한다.

- 실제 생성 추가1회만, 누적 S2d1+S2e1=최대2회. gt02~10, warmup, retry, 다른 모델/조건 sweep0. 성공해도 이번 계약에서 자동 확대하지 않는다.
- S2d deadline1795843851.394598은 이미 종료됐으며 부모 ledger/clock를 재개·초기화하지 않는다. 새 S2e 별도 experiment와 ledger로 첫 dispatch부터12분 wall cap, HTTP480초/watchdog510초/정리60초를 둔다. 단일 요청·실패 latch·예약 뒤중단도 사용시도로 보존한다.
- metadata 최대160회·각5초, /ps5초 간격, adapter 전후 tags도 포함. 부모 metadata30은 별도 누적190이내로 보고한다. 새로운 소유 Ollama 서버 시작 최대1회, 부모1회도 이력에 남긴다. 기존 설치 서버/모델만 사용하고 새 다운로드/타모델 unload0이다.
- 기존 S2d의 normal30초/디스크2GiB/RSS8GiB/critical pressure 또는 계측실패 중단·warning후복귀·정리관찰·외부작업 충돌·소유권 조건을 그대로 따른다. 새로운 runtime로 계측을 생략하지 않는다. client 종료와 서버 추론 종료는 분리하며 미확정일 때 unload/재호출하지 않는다.
- 현재 metadata의 정확digest와 /show thinking capability를 읽어 기록한다. thinking metadata가 없으면 지원 여부 미확정이지 false 지원으로 단정하지 않는다. identity 불일치·타모델/서버 충돌·자원 점검 실패면 실제호출0으로 끝낸다. 설치된 Ollama 업그레이드는 범위 밖이다.
- 제어시험은1회/12분/metadata160 및 부모변조·재개거부·요청실패·timeout·ownership을 포함한다. 현재 output raw/thinking을 로깅하는 디버그를 켜지 않는다. 응답 내용 대신 정규화된 status/finish_reason/usage/boolean 분리관측으로 실패를 설명한다.

## 결과 검토·완료

gt01 유효 답변이면 기존 필수6개·추가 주장·원문 의미/인용을 Codex가 대조한다. 사람이 승인했다고 표현하지 않는다. 기존 원문/GT는 프롬프트 밖에서 검토에만 사용한다. 결과가 truncated/unsupported/invalid이면 추측으로 원인을 확정하거나 임의 복구하지 않고 이 모드·예산에서 실패했다고 보고한다.

별도 `docs/verification/p032-s2e/`에 구현·설치·독립제어·동결·실제한건·자원/정리·답변 대조·부모보존을 커밋하고 학습 안내에 연결한다. 보고서는 모델 모드/최종답변/근거/검토를 먼저, 상세 실행을 접어서 제공한다. 허용된 모델0 화면 확인만 수행하며 filepicker 우회0이다. 정상 personal/dev push까지가 전달 범위다. 소유 프로세스 정리와 현재 실패상태를 남긴다.

S2e 성공은 gt01 한건의 모드 호환/출력 관찰일 뿐 전체10문항·모델 품질·P032 전체 완료가 아니다. 결과를 plan이 검토한 뒤 후속 확대 계약을 준비한다. Drive/평가기/LLM 청킹/API/8B/main/PyPI는 계속 제외한다.
