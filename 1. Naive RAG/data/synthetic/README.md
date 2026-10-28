# 합성 HR 평가 데이터 v1

모든 문서와 질문은 이 프로젝트를 위해 만든 가상 자료다. 실제 회사 정책이나 개인 정보를 포함하지 않는다.
`chunks.jsonl` 전체가 고정 corpus v1이다. 내용 변경은 파일 SHA-256으로 구분하며, 다중 유효 버전 처리나 실제 HR 제도의 유무를 판단하는 용도로 사용하지 않는다.

이 15개 청크는 수작업으로 작성했으므로 청킹 전의 별도 원문 파일은 없다.
이후 원문부터 청킹까지 학습하기 위해 새로 작성한 Markdown·PDF는 [원문 v2 안내](../source-v2/README.md)에서 찾을 수 있다.
현재 UI는 이 폴더의 [chunks.jsonl](chunks.jsonl)을 기본으로 사용한다.

## 구성

- `chunks.jsonl`: 15개 청크, 생일 휴가·연차·재택근무·복지·교육·출장의 6개 문서.
- `queries.jsonl`: 14개 질문, answerable 11개와 unanswerable 3개.
- `example_rankings.jsonl`: CLI 실행 확인을 위한 수기 예시. 검색 엔진의 측정 결과가 아니며 품질 기준선으로 쓰지 않는다. q08은 빈 검색, q12는 근거 없는 질문에 비관련 결과가 반환된 경우다.

## JSONL 스키마

각 줄은 JSON 객체 하나다. 필수 필드는 아래와 같으며 추가 필드는 평가에 사용하지 않는다.
UTF-8로 읽으며 빈 파일·빈 줄·중복 JSON 키·비표준 NaN/Infinity는 거부한다.

| 파일 | 필드 | 계약 |
| --- | --- | --- |
| chunks | `chunk_id` | 파일 내 고유한 비어 있지 않은 문자열 |
| chunks | `document_id`, `version`, `title`, `text` | 비어 있지 않은 문자열. 같은 문서의 여러 청크는 document_id를 공유 |
| chunks | `source`, `synthetic` | `synthetic://` 출처, 반드시 JSON true |
| queries | `query_id`, `question` | 비어 있지 않은 문자열, query_id는 고유 |
| queries | `answerability` | `answerable` 또는 `unanswerable` |
| queries | `relevance` | 존재하는 chunk_id → 정수 0~3. bool·실수는 거부 |
| rankings | `query_id` | 질문마다 정확히 한 번. 누락·중복·알 수 없는 ID 거부 |
| rankings | `chunk_ids` | 순서가 있는 고유한 기존 청크 ID의 배열. 빈 배열 허용 |

answerable 질문에는 등급 1 이상 근거가 적어도 하나 필요하며 unanswerable 매핑은 비어 있어야 한다.
0은 비관련, 1은 주변 근거, 2는 부분적인 핵심 근거, 3은 질문에 직접 답하는 근거다. 매핑에 없는 청크도 비관련이다.
평가기 자체는 임의 크기의 유효 fixture를 허용하며, 12청크·10질문 조건은 이 배포 데이터의 조건이다.

## 수작업 정답 검토

| 질문 | 직접 근거 | 혼동·평가 포인트 |
| --- | --- | --- |
| q01 | birthday-eligibility | 생일 포인트 지급은 휴가 자격 근거가 아님 |
| q02 | birthday-window | 연차 이월 규정을 생일 휴가에 적용하지 않음 |
| q03 | birthday-eligibility, birthday-window, birthday-request | 자격·기간·신청 세 근거 모두 필요 |
| q04 | annual-accrual | 1년 미만 연차 발생 |
| q05 | annual-request | 생일 휴가·출장 신청 기한과 구분 |
| q06 | annual-carry | 연차 이월 한도와 만료 |
| q07 | remote-eligibility, remote-days | 보안 조건의 주변 근거 remote-security는 등급 1 |
| q08 | remote-security | 공용 컴퓨터 금지 및 VPN |
| q09 | welfare-birthday | 별개라는 직접 근거 3, 신청 승인 2, 휴가 자격 1 |
| q10 | welfare-meal | remote-days는 근무일 구분의 주변 근거 1 |
| q11 | annual-halfday | 연차 반차와 생일 휴가 분할 구분 |
| q12–q14 | 없음 | 배우자 출산 휴가·퇴직금·반려동물 동행 휴가를 설명하는 근거가 corpus에 없음 |

근거 없음은 이 corpus에서 답을 확인할 수 없다는 뜻이다. 실제 제도가 없다는 결론이 아니다.
