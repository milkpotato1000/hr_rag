# P013 재개 계약 — M1 16GB 단독 모델 실행

상태: READY after exact adoption. 날짜: 2026-11-27. 사용자 요청은 “P013 재개 플랜 잡고 dev에 전달…8B 단독 실행 메모리부터 확인하고, 4B 답변 생성 후 8B로 평가”다. 이 계약은 P013 미완료 범위의 자원 중단 복구·새 실행 시간 구간·모델 생명주기·S4 실행 순서를 한정 개정한다. 기존 정답·라벨·모델·채점 기준과 C1~C4 완료 조건은 유지한다. main/하네스/타 프로젝트, 모델 다운로드·14B·외부 API·자동 모델 전환은 범위 밖이다.

## 1. 중단 근거와 보존

- dev 관찰 기준: `6cad4c6d1ee36ef0c9ae864a84b8299fd069bd11`, clean, personal/dev 일치.
- 이전 READY: `0cb6497a63c3c79e2b11615f6897f3f4f8f7eb85`, adoption `9d7cb4b`.
- `p013-run001` manifest 내부 digest `007f38f7c5ae6f6de30baff8762717db87b3e757218457b334bc14109e8fb514`.
- 실제 파일 SHA256: manifest.json `77f160f0b91620fec83dfd8c2dae988753532c870269f009a9d58092e04e7be0`, ledger.json `ff1ea3dbb31f946c717b35549229d4cd878278ed04cb2e9b4673c5e025b519ca`, calls/001.json `570bb990dfc8f648578d772c0d73aa09daf4e4918d3e78f3bea19bb886fe8418`, cases.json `6af42b60acbdea8278bf2fad3f3787e4e6f10c00f101764fac8713040220cea1`, expectations.json `1e9d762faf03177f9dcb5f6affc7547ccd8efaf455b027795040eaeae64209bc`.
- `extract01-r1`은 실행 완료·두 사실 정확 일치. 21.76초, 입력287/출력146토큰. sampled Ollama RSS 최고6,239,797,248bytes, OS pressure4가4회 발생했다. `pending=null, unresolved=true`이며 timeout 미확정이 아니라 완료된 요청에서 발생한 자원 중단이다.
- run001의 원본·ledger·stop·code·manifest·보고서를 모두 보존한다. `unresolved=false`로 덮어쓰지 않는다. 새로운 `p013-resume001` 디렉터리와 append-only recovery event가 parent hashes·완료 요청1건·사용자 재개 지시·새 exact plan SHA·변경 목적·새 코드 hash를 연결한다. 이 연결을 검산하는 새 executor만 이번 resource stop을 한정 승계할 수 있다.
- 다른 pause/OPEN decision, timeout/provider 진행 여부 미확정, 데이터/코드 변조는 이 승인으로 해제되지 않는다. parent가 바뀌거나 새로운 writer가 있으면 재검토한다. 이전 S1/C1 증거는 내용이 같다는 검산 후 참조하되 변경된 runtime/adapters는 새 테스트로 검증한다.

## 2. 새 시간 구간과 호출 예산

이전4시간 구간은 종료됐다. 이번 사용자 재개 지시와 exact adoption에 근거해 **단 한 번의 새4시간 wall 구간**을 승인한다. resume ledger에 최초 모델 작업 dispatch 직전 timestamp/deadline을 영속 기록한다. 재시작·쉘 재실행·대기·미사용 예산으로 deadline을 갱신하지 않는다. 최초 dispatch 후 프로세스 종료/기기 재시작도 시간을 소비한다. 오프라인 준비는 모델 작업 전에 마친다.

| 작업 | 이번 남은 최대 | 이전 사용 | 누적 최대 |
| --- | ---: | ---: | ---: |
| S2 추출(첫 잔여 요청을 메모리 probe로 사용) | 15 | 1 | 16 |
| S3 고정 판정/매칭 | 68 | 0 | 68 |
| S4 query embedding | 20 | 0 | 20 |
| S4 4B 답변 생성 | 20 | 0 | 20 |
| S4 8B 평가(추출20/판정80/매칭80) | 180 | 0 | 180 |
| **업무 모델 요청** | **303** | **1** | **304** |
| 명시 unload 제어 요청 | 4 | 0 | 4 |

이번 최대 provider 작업은307건(업무303+unload4), parent 포함308건이다. 읽기 메타 조회/1초 모니터링은 inference 요청이 아니며 별도 횟수 기록한다. 빈 프롬프트 preload·추가 warmup·재시도·sweep는 없다. 첫 잔여 `extract01-r2`가 실제 inference를 하는 메모리 probe이자 S2의 두 번째 반복이다. 성공/실패와 무관하게1건 소비하며 재호출하지 않는다. 기존 `extract01-r1`은 재실행하지 않는다. 자동 재시도0, 모델 요청 병렬1. 단계별 미사용 예산 전용 금지.

4회 unload는 순서대로 S2/S3 8B, S4 embedding, S4 4B, S4 8B의 각 체류 종료에 최대1회다. 중단 시 해당 체류의 unload 슬롯을 정리에 사용할 수 있으나 추가 재시도하지 않는다. timeout으로 실제 inference 완료 여부가 불명확하면 unload도 자동 실행하지 않는다. wall 만료 후에는 신규 inference 금지; 자신이 독점 소유하고 완료가 확정된 모델의 종료 정리만 남은 unload 슬롯·30초 timeout 이내에서 허용하고 별도 기록한다.

## 3. 먼저 확인할 8B 메모리 게이트

### 오프라인 준비

recovery event/합산 카운터/단계 순서/단독 모델 ownership/미확정 중단/새 deadline·불변성·CLI와 재생을 구현하고 네트워크 차단 fixture 테스트를 통과시킨다. 실제8B 실행은 새 runtime·검토 manifest·고정 입력·새 S1 증거가 커밋된 뒤 시작한다.

### 적재 전

- 실제 Apple M1/물리 메모리16GB와 OS/Ollama·모델/template/tokenizer를 기록한다. 기존 모델 digests와 Ollama0.40.8 계약이 다르면 임의 설치/업데이트/태그 치환하지 않고 mismatch로 보고한다.
- `ollama ps` 상당의 조회에서 loaded models0 확인, 단일 runner lock 확보. 사용자 앱/다른 세션/외부 Ollama 호출을 강제 종료하지 않는다. 다른 모델/요청이 관찰되거나 단독 사용을 확인할 수 없으면 dispatch하지 않는다.
- 30초 동안1초 간격으로 OS pressure1(normal), 계측 정상, 기존 RSS12GiB 상한 미초과를 확인한다. 조건 미충족 시 모델 미호출 상태로 결과만 남기고 멈춘다. 빈 RAM8~10GB라는 추정치를 보장 조건으로 사용하지 않는다.
- 물리 메모리, vm_stat 요약(페이지 크기·free/inactive/purgeable/compressed/wired), swap 사용량 전후, Ollama RSS, loaded model/size/size_vram/context 정보를 가능한 필드 그대로 기록한다. GPU 실사용·총 메모리를 RSS와 합쳐 중복 계산하거나 샘플 최고치를 진짜 peak로 부르지 않는다. 핵심 pressure/RSS 계측 실패는 중지; 부가 진단 필드의 미지원은 unavailable로 표시한다.

### 적재·추론·유지 관찰

고정 `extract01-r2` 요청 하나만 실행하고 Qwen8B 외 모델이 적재되지 않았는지 확인한다. 입력/출력·context8192·think=false·seed42·temperature0 등 의미 설정을 유지한다. 이 요청부터 transport의 `keep_alive`만 기존0에서300초로 바꾼다. 원래 payload와 바뀐 payload 모두 hash/field diff를 저장한다. 변경 허용 키가 keep_alive 하나인지 기계 검산하며 동일 payload 반복이라고 부르지 않는다. 이전 run과는 같은 의미 설정·다른 생명주기 조건의 비교임을 보고한다.

적재부터 요청 종료 후60초까지1초 간격 모니터링한다. 모델이 유지된 상태를 ps로 확인하고 최종30초가 pressure1인지 검사한다. 중간 pressure2(warning)는 기록하되 이것만으로 critical이라고 부르지 않는다. 한 번이라도 pressure>=4, RSS>12GiB, 핵심 계측 실패면 memory gate FAIL. 정상 완료된 첫 호출도 자원 실패 기록을 지우지 않는다. 끝까지 warning이면 inconclusive로 멈추며 성공으로 표시하지 않는다.

메모리 PASS는 **이 단독 적재·짧은 입력의 관측 통과**일 뿐 최대 문맥·오랜 연속 실행의 안전 보장이 아니다. S2/S3/S4 전체에서도 같은 중지 모니터를 유지한다. probe의 JSON/span/의미 검토는 memory gate와 별도다. probe가 의미 검토 대기/실패면 승인된 기존 S2 게이트에 따라 후속 호출 확대를 멈춘다.

## 4. 모델을 순서대로 사용

| 체류 구간 | 적재 모델 | 작업과 다음 구간 조건 |
| --- | --- | --- |
| A | Qwen3:8b 하나 | memory probe → 잔여 S2 → S2 통과 시 S3. S2/S3 전체 통과 후 unload·loaded0 확인 |
| B | bge-m3 하나 | 고정10질문/두 청킹의 query embedding 최대20회·Dense 검색 및 실제 생성용 context 선택을 저장. 기존 색인 사용, corpus 재임베딩0. unload·loaded0 확인 |
| C | Qwen3:4b 하나 | 저장된 검색 문맥으로 LangChain 답변 최대20개 생성·dispatch trace 저장. 숨은 query embedding 재호출0. 전체 생성 상태/실패를 확정하고 unload·loaded0 확인 |
| D | Qwen3:8b 하나 | 승인 데이터와 저장된 실제 답변/전달 문맥으로 추출·Faithfulness·Correctness 평가. 생성4B/embedding 호출0. 종료 후 unload·loaded0 확인 |

구간 간 normal pressure30초/소유권 검사를 반복한다. 한 구간을 시작한 뒤 앞 구간으로 돌아가 모델을 교대로 부르지 않는다. 자동 eviction에 기대지 않으며 원래 서버의 전역 설정이나 OLLAMA_MAX_LOADED_MODELS를 바꾸지 않는다. 현재 구간이 소유한 정확 digest의 모델만 unload할 수 있다. 다른 모델이 나타나면 충돌 기록·신규 호출 중지, 타 모델 자동 unload 금지.

기존 keep_alive0은 매 요청의 cold load를 반복한다. 이번에는 업무 요청마다300초로 한정 유지하고 구간 끝에서 명시 unload한다. idle 만료로 모델이 사라지면 기록하고 중지한다. 자동 preload/reload loop로 호출 예산을 우회하지 않는다. 정상 종료 시 unload 확인을 남기며 provider가 keep_alive를 따르지 않으면 실패로 보고한다. 병렬 추론 및 여러 모델 동시 상주는 없다.

S2는 parent의 exact pass1건 + 잔여15건으로16개 고정 사례를 검증한다. 이전 성공을 자원 안정성 PASS로 승계하지 않는다. 의미적으로 다른 표현은 기존 독립 검토 절차를 유지하며 모델 자체 판정으로 자동 승인하지 않는다. S3 gate는 기존68개 전건 기준을 유지한다. 실패하면 정답을 바꾸거나 S4로 넘어가지 않는다.

## 5. S4 저장·연결·재현 계약

- B구간 retrieval artifact에 question ID/text/hash, embedding model/digest/query vector hash, 기존 P007 두 config·index fingerprint/chunks/canonical hash, Top-K5·문자8000 예산, candidates/contexts/excluded·순서·실제 텍스트를 고정한다. 같은 질문 임베딩 캐시 재사용은 동일 모델/질문 bytes/hash일 때만 허용하며 hit/miss를 기록한다.
- C구간 adapter는 이 artifact를 읽어 기존 LangChain 생성 경로를 재사용한다. 검색을 몰래 다시 실행하거나 생성 prompt·schema·4B digest·token 한도를 바꾸지 않는다. 실제 `generation.request`/messages와 선택 context의 연결을 검산한다. GT/판정 라벨 유출0을 테스트한다.
- D구간은 **실제로 전송된 context snapshot**으로만 Faithfulness를 평가한다. 전체 원문과 retrieval 후보를 보충하지 않는다. Correctness는 승인된 GT 필수/보충 정책을 사용한다. 생성 실패·미호출은 평가 제외 사유와 함께 보고한다. 한도를 넘는 문맥은 실패로 남기고 조용히 자르지 않는다.
- 새 report는 parent의1회와 이번 사용량/제어 호출/유지 시간/초기 적재·추론 지연/최고 sampled RSS·pressure·swap 변화를 분리한다. 단독 메모리 게이트, S2/S3 의미 게이트, 실제 RAG 점수를 다른 상태로 표시한다.
- 독립 bundle에는 parent 증거와 새 recovery/계보·manifest·ledger/코드·승인 입력·retrieval/generation snapshots를 포함한다. 네트워크 없이 원본과 새 결과 모두 재생한다. old run001의 unresolved를 숨기지 않고 “당시 중단; 승인된 후속 실행 별도”로 표시한다.

## 6. dev 필수 검증과 완료 경계

1. parent hash 불일치, pending/timeout 미확정, 다른 OPEN/stop, 중복 case/이미 실행한 r1, consumed recovery ID, wall 만료, 합산304/제어4 상한 초과, 두 runner 동시 실행을 거부한다.
2. memory probe normal→critical→normal이어도 FAIL 보존, 12GiB 이하 critical 중지, warning 지속 inconclusive, 누락 계측 중지, ready 전 실호출0을 독립 fixture로 검증한다.
3. 소유하지 않은 모델 unload 금지, 구간 B/C/D에서 잘못된 모델 호출 금지, keep_alive 외 payload 변경 거부, idle 만료/타 writer 감지 시 중지, unload 실패 처리 검증.
4. cached retrieval과 원래 경로의 ID/order/context/메시지 일치, stale vector/hash/설정 불일치·GT 유출 차단, 실제 dispatch trace 검사, 생성 실패 제외·독립 offline replay/기존 preparation 회귀·원본 보존을 검증.
5. 실제 메모리 관찰과 단계 결과가 준비돼야 해당 PASS를 기록한다. 소규모 probe 통과만으로 P013 완료 금지. C1~C4는 기존 기준 및 이 재개 검증을 충족해야 한다.

새 critical/불명확 상태가 발생하면 다음 호출 없이 중단하고 사용자가 조치할 최소 사항만 보고한다. 자원이 부족하다고 자동으로4B 평가·14B·다른 서버로 전환하지 않는다. 한 번의 재개 grant가 이후 반복 재개까지 승인하지 않는다.
