# P032 실제 RAG 통합 검증 설계

2026-11-28 DRAFT. 다운로드·추론·서버 시작·계정 연결을 실행하지 않는다. P031 완료 후 정확 실행 계약과 READY 채택이 필요하다. P013 평가기·로컬 메모리 recovery 보류를 우회하지 않는다.

## 고정 자료와 질문

기존 `2. Document Chunking/data/source-v4/output/pdf/hr-handbook.pdf`를 후보로 선택했다. 실제 파일은227474bytes, SHA256=1a199799cc3807fdaa6e0390784d58697d38a83d4708b2967ddead72dc4f9369다. 기존 P007 source-profile은23쪽·canonical38582문자·79제목을 기록한다. 이는 기존 파서의 관찰값이며 새 generic snapshot에서 같은 canonical/offset이라고 가정하지 않는다. 설치물로 다시 파싱하여 페이지·제목·원문 누락·정규화 차이를 대조해야 한다.

run004의10개 질문·필수/보충 주장과 별도의 P013-human-approval.json을 읽기 전용 참고로 사용한다. packet 내부 후보 status는 당시 검토 이력이며 이후 승인 기록과 구분한다. packet 파일 SHA256=e081e372ff089b5ad6eae334b29924438359993fdfa534d67578af9785b1aa7b, 승인에 연결된 내부 packet_sha256은 별도 필드다. 파일 bytes hash와 내부 digest를 혼동하지 않는다. 승인된 GT를 수정하거나 평가기를 실행하지 않고, 각 질문의 근거 문장·조항을 새 snapshot의 exact source span으로 다시 연결한다. 이전 canonical offset을 그대로 복사하지 않는다.

직접 대조한 내부 packet_sha256은 ddbc3975cc2dd728bc6950fed1a507ed03223cbdea94987c572b6cc2f0bde235이며 승인 기록의 run004_packet_sha256과 일치한다. 기존 승인을 새 모델의 출력 품질 승인으로 확대하지 않는다.

처음 검증은 질문 수를 줄인 smoke와 전체10개를 구분한다. smoke 성공만으로 전체 비교를 완료하지 않는다. 검색 관련성 qrels와 원문 필수 fact/span은 generation/NLI 프롬프트에 넣지 않으며 검색·리랭킹 성능 및 전달 문맥의 누락을 측정하는 데 사용한다. 새로 작성하는 qrels는 작성/검토 근거를 별도 남긴다.

## 순차 검증 후보

| 단계 | 고정할 것과 바꿀 축 | 확보할 증거 |
| --- | --- | --- |
| A 준비 | P031의 고정 revision·파일 recipe, 독립 설치 | 원본 hash·native/변환 출처·검사·소요 시간·디스크·자원·실패. 실제 다운로드와 tiny fixture를 구분 |
| B 검색 기준선 | 같은 snapshot·규칙 청크·질문, E5-small/BGE-M3와 BM25/Dense/Hybrid | 실제 index/query 전처리·차원·원본 근거·qrels 지표·실패·cold 지연. 작은 모델부터 단독 실행하고 종료를 확인 |
| C 리랭커 | 같은 저장 후보 N·K·문맥 예산, none/mMiniLM/BGE | 후보 밖 재검색0, 실제 pair 점수·순위·top-K/문맥 근거 회수와 시간·메모리 비교 |
| D 답변 | 동일하게 저장된 전달 문맥, 선택된 local/API 생성 profile | 실제 request identity·답변·인용·에러/보류, 질문의 필수 항목과 원문을 대조한 검토. 자동 Faithfulness/Correctness 평가기는 실행하지 않음 |
| E 청킹 | 같은 source·질문·검색/생성 profile, fixed/recursive/structure/semantic/LLM | 실제 경계·overlap·원문 보존·중복·근거 회수·작업량, 모델0 replay/derive. 경계 생성 비용과 검색/생성 비용을 분리 |
| F 사용자 경로 | 선택한 결과를 설치 CLI/UI에서 재생하고 코딩 도구 실습으로 연결 | 문서 링크·모델 설정→최종 답변 경로, 허용 UI 검증·설치 출처·실패 복구와 지원 한계 |

모든 축을 곱한 무제한 실행은 하지 않는다. 대표 기준선을 고정하고 한 축씩 바꾸는 행렬·최대 작업 수를 READY 전에 산출한다. E5/mMiniLM만 통과했다고 BGE/LLM 청킹의 실제 성능까지 검증했다고 쓰지 않는다. 큰 모델이 자원 한도를 넘으면 해당 상태를 실패/미지원 환경으로 명시하고 입력 축을 몰래 다른 모델로 바꾸지 않는다. 성공 threshold를 보고 난 뒤 유리하게 바꾸지 않는다.

## 실제 모델과 권한 경계

embedding/reranker는 P031 네 공식 후보와 pinned recipe를 사용한다. CPU 단일 owned worker, 고정 SDK·batch1·작은 token 한도로 시작하고 actual RSS/OS pressure·경과 시간·worker 종료를 관찰한다. 전체 PDF·모든 질문으로 늘리기 전 작은 사례를 검사한다. 한도·사전 여유 조건·업무/제어 요청 수·전체 deadline은 P031 구현과 현재 환경을 대조해 READY에서 확정한다. 다운로드 완료와 메모리 적재를 구분하고 다른 앱을 종료해 여유 공간을 만드는 방법은 쓰지 않는다.

생성 모델의 기존 qwen3:4b alias는 과거 lock에서 Qwen3-4B-Thinking-2507 원본을 가리키므로 일반 Qwen3-4B와 혼동하지 않는다. 과거 digest만 복사해 현재 서버/실행 가능을 입증하지 않는다. 새 P031 inspect 결과와 실제 선택·설정이 필요하며, 모델 pull/start/unload·8B probe·기존 grant 소비를 이 초안에 포함하지 않는다. 로컬 생성·LLM 청킹 실행 범위와 P013 중지 경계를 READY 전에 명시한다. API는 사용자가 선택한 모델·자격/예산으로만 호출하며 키 값은 문서/CLI 인수/Git에 남기지 않는다. 키가 없으면 해당 실제 API 검증은 미실행으로 남기고 fake 결과를 실호출로 표시하지 않는다.

Google Drive 실제 연결은 사용자가 지정한 테스트 문서와 본인 인증 설정이 필요하다. 현재 링크 질문은 답변 대기이며 예제 placeholder를 실제 연결로 간주하지 않는다. 로컬 규정집 시험과 독립 진행하되 로컬 파일 성공으로 웹하드 링크 E2E를 완료하지 않는다. P029 차단된 filepicker 경로도 그대로 미완료로 두고 정책을 우회하지 않는다.

## 다음 준비 작업

P031 최종 도구/설치 artifact를 확보하고 실제 준비 가능한 모델·기존 선택 LLM·환경/자원 관찰 방법을 대조한다. generic parser의 새 source 구간과 승인 참고 자료의 매핑을 검토하고, 비교 행렬과 독립 기대값·최대 호출을 고정한다. 남은 사용자 문서/설정 입력은 필요한 시점에 연결한다. 현재는 기획 초안이며 실제 요청·다운로드·모델 실행0이다.
