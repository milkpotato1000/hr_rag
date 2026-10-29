# P011 최종 검토 — LangChain 채택

판정: **ADOPT_LANGCHAIN**. 2026-10-29T10:54:54+09:00 Codex가 고정 원문·실제 출력·다운로드 결과·회귀 증거를 대조했다. 아래 제한된 비교에서 기존 구현 대비 저하가 관찰되지 않았으므로 사용자의 조건부 위임에 따라 후속 기반을 LangChain으로 선택한다. 기존 Naive 실행 경로와 비교 UI의 Direct 기본값은 유지한다.

## 무엇이 바뀌었나

기존 `1. Naive RAG/`는 비교 기준선이다. 독립 후보 `1. Naive RAG/variants/langchain/`에 corpus 읽기 → 검색 → 불변 문맥/메시지 → 무문맥 보류 또는 생성1회 → 검증/전체 원문 조립을 명시적인 Runnable 단계로 구성했다. 같은 BM25·BGE-M3·Qdrant·Qwen·프롬프트·ID-only 응답 계약을 사용한다. provider 교체, 자동 재시도, Hybrid, 프롬프트 보정은 포함하지 않는다.

후보 CLI의 `--implementation direct|langchain`, API 선택, `http://127.0.0.1:8001/`의 두 구현 비교 및 JSON 다운로드를 제공한다. 원래 UI는8000이다. 후보는 같은 서버 잠금 안에서 직렬 비교하고 한쪽 실패도 보존한다. 실제 UI에서 복수 근거 답변과 근거 없는 질문의 보류, 입력 잠금/해제, 결과 교체, 다운로드를 확인했다. 한쪽 오류와390px 화면은 별도 로컬 fixture로 확인했다.

## 품질·검색 결론

사전 고정20질문 ×3회 ×2구현 =120 warm슬롯을 원문 rubric으로 검토했다. 원본의14질문, PDF질문, 식대BM25, 추가4질문을 포함한다. 작은 추가 세트이며 독립된 대규모 holdout은 아니다. 각 질문별3회 지표를 비교했으며 질문 간 성적 상쇄를 허용하지 않았다.

| 지표 | Direct60회 | LangChain60회 |
|---|---:|---:|
| 필수 사실 충족 |159/186|159/186|
| 모든 필수 사실 충족 |30|30|
| 부분 답변 |15|15|
| 과도 보류 |3|3|
| 적절 보류 |12|12|
| 선택 인용의 주장 지지 |171/177|171/177|
| warm 실행 오류·모순·허구 |0·0·0|0·0·0|

답변과 인용의 모델 선택도 이번 반복에서는 동일했다. 생일 휴가의 연1일 누락, 재택 예외·승인 주체 누락, 보안 근거가 있어도 보류하는 기존 한계는 양쪽에 남았다. 프레임워크 변경이 답변 품질을 개선했다는 결과가 아니다. [원문 의미 검토](quality-review.md), [질문별 근거](manual-reviews.json)를 함께 읽는다.

고정벡터326조건 및 실제18질문의 임베딩 입력/출력과 그 벡터를 사용한326조건이 일치했다. 실제 반복 호출에서도 검색 순위·점수, 전달/제외 청크, 직렬화한 HTTP 요청, 원문 인용 bytes를 대조했다. [parity](parity.json), [live parity](live-parity.json), [실제 임베딩](embedding-parity.json), [재측정 포함 비교](controlled-comparison.json)에 증거가 있다.

## 속도·비용과 최초 실패

속도 향상은 확인되지 않았다. Dense warm의 질문별 쌍별 중앙값 차이는 약+0.09~0.49초였다. Cold의 쌍별 중앙값 차이는 식대+0.33초, PDF+0.58초, 생일 종합+0.35초였다. 각각3쌍의 관찰이며 일반적인 성능 보장은 아니다.

BM25의 큰 차이는 순서/프롬프트 캐시 영향을 받았다. 교육휴가 질문은 첫 번째 구현의 prompt_eval이 약3.2초, 두 번째는 약0.08초였고 구현 순서를 바꾸면 이 관계도 바뀌었다. 질문당3회는 선행 위치2:1이므로 +35~47% 같은 비율을 LangChain 비용으로 해석하지 않는다. 전체 시간과 겹치는 세부 시간을 합산하지 않는다. [시간·자원 보고서](latency-resource-report.md), [전체 분포](controlled-comparison.json), [BM25 순서 관찰](bm25-order-observations.json) 참조.

격리 환경 파일 크기는86.34MB→135.66MB(약49.31MB 추가), 단일 import 관찰은12.51ms→229.73ms였다. 생일 종합 warm의 worker peak RSS 중앙값은91.06MB→113.89MB였다. RSS는 Python 프로세스만 측정했고 공유 모델 서비스 메모리는 제외했다. 기존 pin 변경 없이 추가 패키지를 설치했다. [resource-report](resource-report.json), [환경](install-report.json), hash lock에 상세가 있다.

최초 cold18슬롯 중 LangChain4건에서 모델 로드500이 발생해 먼저 KEEP_DIRECT를 기록했다. OS 절전 공백 근거를 확인하고 코드를 바꾸지 않은 채 사전 등록한 repair-plan에 따라 영향받은 warm3질문의 양쪽 전체 반복과 cold18슬롯을 다시 실행했다. 프로세스 범위의 idle-sleep 방지 아래 재측정36슬롯은 모두 성공했고 출력은 검토 원본과 같았다. wall/monotonic 최대 차이는 약0.005ms였다. 최초 실패와 초기 판정은 삭제하지 않았다. 일부 초기 warm 동안 다른 로컬 검사가 실행됐고 OS 파일 캐시도 비우지 않았으므로 작은 시간 차이를 프레임워크의 인과 효과로 단정하지 않는다.

독립 임시 복사본은 뒤늦은 smoke에서 색인 metadata가 없어 실패했다. 제거 원인은 확정하지 못했다. 불완전 경로와 실패를 보존하고 검증된 동일 색인을 다시 snapshot한 후 PDF·보류 smoke 및32개 후보 회귀를 통과했다. 제품 retry/fallback이나 테스트 제외로 우회하지 않았다. [실패·수정 기록](failures.md), [초기 판정](adoption-decision.initial.json), [복사 복구](copy-index-repair.json) 참조.

## 검증 완료

| 검증 | 결과·증거 |
|---|---|
| 원본93파일·과거P001~P009증거 보존 | PASS; preservation-check.json, copy-manifest |
| 원본/후보/독립복사 두 색인의 논리 hash·manifest | PASS; index-final-check.json |
| 기존 단계107 / 후보 기존107 / 추가32 | PASS; baseline-tests-pass.log, candidate-tests-pass.log, langchain-tests-http.log |
| 루트19 / 하네스12 | PASS; root-tests.log, harness-tests.log |
| 독립 복사107+32 및 색인 복구 후32 | PASS; copy-tests*.log, copy-regression.json |
| 실제CLI·API·브라우저·오류/좁은화면·JSON | PASS; smokes/, browser-check.json |
| 계약 동등성·원문 의미·실패 보존 | PASS; parity/quality/controlled 보고서 |

실제 생성 dispatch는 총189회로320회 상한 이내다. 실패한 로드는 실제 전송으로 세고, 색인 미존재로 생성 이전에 실패한 smoke는0회로 기록했다. mock 회귀와 실제 임베딩 전용 검사는 생성 dispatch에 포함하지 않는다. ledger.jsonl을 보존한다.

## 정확한 후속 기반

- 채택 plan: `63f9d259d76f322f1c6112b4306d0eb6941064a6`.
- 기준 원본: `58e8eb793b95c524c256c0206e37aa15ff99c6ff` / `1. Naive RAG/`.
- 후보 소스 고정 커밋: `37acda801695992cf96ee237fba7cdee8a99bb8b` / `1. Naive RAG/variants/langchain/`.
- 실행 진입점: `scripts/rag_langchain.py`, SHA256 `273698d2f34bd4017722a9fbc92d77032b2352b44936c49a158213e1c367303c`.
- 비교 protocol 사전 고정: `f008d32fcb5059a7e08d7b1a727f4bea7b8de261`.
- 최종 판정/증거는 이 문서를 포함하는 완료 커밋을 사용한다. 후보 소스 커밋 이후 제품 코드는 변경하지 않았고 최종 판정 사본만 추가했다.
- 후보의 copy-manifest.json 및 adoption-decision.json을 함께 확인한다. 복사 시 `.venv`, `.runtime`, `__pycache__`는 제외하고 README의 환경/색인 절차를 따른다. 공유 로컬 모델 서비스는 명시적으로 재사용한다.

미해결 P011 차단 사항은 없다. 다음 P010 Hybrid는 이 판정과 파일 hash를 검토해 자체 계약을 준비·채택한 뒤 진행한다. 이번 완료로 P010이나 설치형 하네스를 자동 착수하지 않는다. Hybrid 이후 PDF reader→청킹 실습 로드맵을 유지한다.
