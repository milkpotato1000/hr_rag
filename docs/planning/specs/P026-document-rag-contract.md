# P026 일반 문서 RAG 통합 계약 v1

## 목표와 파일 경계

P025의 실제 provider를 문서→청크→검색→답변에 연결한다. 신규 `rag_package`의 document/chunk/retrieval/rag 모듈과 `python -m rag_package` CLI, `examples/rag/`, `tests/rag_package/`, `docs/learning/rag-package/document-rag.md`가 범위다. 내부 파일 분리는 dev가 정한다. 기존 번호 단계·evaluation·P025 공개 API의 동작 계약은 보존한다. P025에 버그가 있으면 의미 변경 없이 별도 근거/회귀로 수정하며 P013 runner/lock/GT를 수정하지 않는다.

새 공통 모듈은 큰 학습 단계의 번호를 대체하지 않는다. P007/Naive의 순수 알고리즘을 선별 복사·수정하면 `rag_package/provenance.json`에 원본 commit/path/hash와 변경 이유를 남긴다. 고정 synthetic/source-v4 허용 검사를 약화시키거나 기존 모듈 global path를 바꾸지 않는다. 생략된 기능은 명확한 unsupported 오류이며 silent BM25 fallback 금지다.

지원 Python 3.10+. TXT/Markdown/청킹/BM25는 표준 라이브러리, PDF만 pypdf==6.21.2 선택 의존성이다. 기존 ingestion lock의 wheel/hash를 재사용하고 새 requirements 파일에 pin/hash를 명시한다. 이번 검증은 기존 `2. Document Chunking/.venv`의 설치된 Python/pypdf로 수행하며 새 설치/다운로드가 필요 없다. pypdf 미설치는 PDF 경로만 명확히 실패하고 텍스트 경로는 동작한다. 설치 패키지·깨끗한 환경 검증은 후속이다.

## CLI와 기본 실행 경로

- `snapshot --sources <JSON> --out <새 디렉터리>`: 명시 파일 목록을 읽고 immutable snapshot을 만든다.
- `build --snapshot <디렉터리> --config <JSON> --out <새 디렉터리>`: 청킹/BM25 corpus artifact를 만든다.
- `ask --run <build 디렉터리> --config <JSON> --question <문자열> --out <새 디렉터리> [--execute]`: 기본 preview는 근거·실제 예정 messages만, execute에서만 provider를 부른다.
- `compare --snapshot ... --configs <2개 이상 JSON> --questions <JSON> --out ... [--execute]`: 같은 질문/원문에 각 설정으로 build/ask하고 비교표 JSON/Markdown을 만든다. 기본 preview, 실제 생성은 명시 execute.

CLI 이름/옵션은 위 인터페이스를 유지한다. 도움말에 preview가 모델/API를 부르지 않는다는 점을 적는다. actual invoke 코드를 포함하되 이번 P026 실행 검증은 injected transport/fake HTTP만 허용한다. 사용자 실문서·키·모델/서버 시작·다운로드·P013 재개는 없다.

기본 학습 output은 Git 제외 `.rag-runs/` 아래의 새 경로 예시다. `.gitignore`에 이를 추가한다. 도구는 기존 artifact를 overwrite하지 않는다. 모든 output 디렉터리는 비존재 경로에 staging/원자적 no-clobber publication으로 기록한다. 실패/needs_review는 별도 status manifest를 남길 수 있으나 ready build로 취급하지 않는다. 호출 후 output 실패 시 자동 재호출하지 않는다.

## 일반 source snapshot

sources JSON은 schema_version:1와 documents 목록. 각 문서는 document_id, title, path, format(pdf/txt/md), synthetic(boolean)을 명시한다. 상대 path는 sources 파일 위치 기준, ID는 유효한 안전 문자열이며 중복 거부. 실제 문서의 synthetic는 false이고 sample만 true. 최대 문서20개, 파일당20MiB, PDF100페이지, 문서별 canonical100만자, corpus 합계200만자, PDF timeout30초. 수치/타입/중복·미지원·깨진 UTF-8/파일 없음은 오류다.

원본 파일 bytes를 snapshot에 복사하고 source metadata/원본sha256·bytes·문서ID·title·synthetic, parser name/version, normalization NFC/LF, raw/normalized page text hashes와 canonical page offset을 기록한다. TXT/MD는 논리 page1, PDF는 물리 1-based page다. page join separator는 LF2개이고 separator 자체는 페이지 원문으로 표시하지 않는다. raw text와 canonical text를 구분한다. 페이지 offset은 Unicode code point이며 bytes/token이 아니다. 저장된 모든 상대 artifact path는 snapshot 밖으로 나가지 않는다. 절대 원본 경로/credential은 public manifest로 자동 복사하지 않는다.

snapshot fingerprint는 문서 identity/원본 hash·parser/정규화·pages/canonical 내용 hash의 canonical serialization에서 결정한다. wall time/output 경로는 identity에서 제외한다. consumer는 사용 전에 manifest identity와 명시 파일 hash/offset·page→canonical 재구성을 확인하며 변조된 snapshot을 사용하지 않는다. parser 실패나 한 페이지라도 text 없음이면 `needs_review`로 표시해 index/ask를 차단한다(스캔/OCR/빈페이지 여부를 설명). OCR·암호 PDF·표 구조 복원은 이번 범위가 아니다. PDF 파싱은 별도 subprocess에서 timeout을 적용하고 무한/손상 PDF 오류를 원문 노출 없이 기록한다.

## 설정·청크 계약

config JSON schema_version:1, chunking{method,size_chars,overlap_chars}, retrieval{method,top_k,context_budget_chars}, llm_config(별도 P025 JSON 경로). 상대 llm_config는 config 파일 기준. 기존 P024 example_only를 실제 config로 허용하지 않는다. 알 수 없는/불필요 필드, bool-as-int/nonfinite·범위 오류를 거부한다. `llm_config`는 build 때 존재 확인/호환 설정 검증만 하며 키·HTTP를 읽지 않는다. ask는 P025 generation role과 response_mode=json_object를 요구한다. 평가 role은 호출하지 않는다.

method는 fixed/recursive/structure, size_chars 100..4000, overlap_chars 0..min(400,size-1). retrieval method는 bm25만 지원, top_k1..100, context_budget_chars1..64000. semantic/LLM chunking, dense/hybrid와 reranker는 계약/연결이 없는 상태로 거부하며 기본값으로 바꾸지 않는다. 기존 P007의 다섯 방식 학습 결과 링크는 유지한다.

- fixed: 최대 size 문자 window, overlap만큼 재사용. recursive: 문단→문장→공백→강제 경계 순서로 최대 길이 내 분할. structure: Markdown ATX 제목과 한국어 `제N장`/`제N조` 줄을 휴리스틱 경계로 인식하고 긴 섹션은 재귀 분할. 제목 미인식 문서는 recursive로 분할하되 detection/fallback 이유를 명시한다.
- 모든 방식이 canonical text를 누락하지 않고 덮는 기본 partition을 만든다. recursive/structure는 base max=size-overlap, 왼쪽 overlap extension 후 최종 길이<=size. structure overlap은 해당 section 시작을 넘지 않는다. document 사이를 합치지 않는다. 빈 공백만의 chunk는 검색에서 제외하되 coverage 정책/제외를 기록하고 나머지 source span을 손실하지 않는다.
- chunk는 stable ID, document ID, canonical start/end, text=canonical[start:end], page intersections, heading_path와 source fingerprint를 가진다. heading은 표시 metadata이며 임베딩/검색 원문이나 인용에 조용히 덧붙이지 않는다. split unit은 최소 사실 단위나 모델 토큰이라고 설명하지 않는다.
- chunk/index fingerprint는 source snapshot+알고리즘 version+청킹 설정+텍스트 hash+BM25 전처리/parameters에서 결정한다. LLM만 바꿀 때 동일 chunk/index identity가 유지된다. chunk 설정/source 변경은 새 identity다. ask의 청킹/검색 방법 설정이 build와 다르면 stale 오류이며 자동 재생성하지 않는다. top_k/문맥 예산/LLM은 query-time 설정으로 달라질 수 있다.

## 검색·문맥·생성

BM25는 기존 P007 unicode-word-v1 NFKC/casefold tokenizer, k1=1.2,b=.75 알고리즘을 재사용한다. 양수 score 후보만 내고 score 내림차순/동점chunk ID 순. title/GT/qrels/answer는 검색 입력에 넣지 않는다. 한국어 형태소 분석 부재 등 한계를 안내한다. index artifact에는 doc/chunk map, settings, index fingerprint를 저장하고 reload hash/identity를 검증한다.

질문은 비공백 문자열 최대2000자. 순위 상위 top_k를 후보로 고른 후 context_budget_chars 안에서 chunk 전체만 담는다. 남은 공간에 안 맞는 chunk는 자르지 않고 excluded=budget로 기록한 뒤 다음 후보를 검사한다. 일부 후보가 빠졌다고 나머지 후보에 없던 내용을 추가하지 않는다. 문자 예산은 chunk text 합계이며 system/prompt JSON 오버헤드·모델 토큰 예산과 다름을 표시한다. 모델 입력 한도를 보장하지 않으며 초과 provider 오류를 별도 기록한다.

동결 프롬프트는 질문/contexts를 데이터로 구분하고 근거에 없는 사실을 만들지 말 것, 부족하면 abstained, 정확 JSON status/answer/citations를 요구한다. contexts에는 chunk ID/text/document/페이지·제목 metadata를 제공할 수 있으나 실제 전송본을 그대로 artifact에 저장하고 fingerprint한다. no-context는 generation0으로 abstained 처리한다. preview도 P025.preview로 실제 변환 messages/hash를 보여주되 key/HTTP 접근0이다.

P025.invoke 결과 complete일 때만 JSON 업무 schema를 검증한다. 정확 필드는 status(answered/abstained), answer(비공백문자열), citations([{chunk_id}]); extra 필드 거부. answered는 unique 인용1개 이상, abstained는 citations=[]를 요구한다. 모든 ID는 실제 전달된 contexts의 ID여야 한다. 모델 quote/page를 신뢰하지 않고 코드가 canonical slice·문서·페이지·heading 정보를 연결한다. 지원되는 인용이 있다는 사실만 검증하며 해당 답변의 의미가 참이라는 Faithfulness PASS로 표시하지 않는다.

malformed/truncated/refused/tool/error/미지원 citation은 answer success로 취급하지 않는다. 결과에는 failed stage/code와 dispatch 여부·provider status를 보존한다. 원문 provider 오류/hidden thinking/credentials를 다시 저장하지 않는다. 업무 schema를 통과하지 않은 model content는 최종 정상 답변에 넣지 않는다. 결과 디렉터리의 정상 messages/content는 사용자 문서를 포함할 수 있으므로 private artifact임을 안내한다.

## 비교와 관찰

questions는 [{id,question}]의 비중복 목록(1..20), configs2..4. source와 질문집 hash 고정. 각 config와 question의 성공/실패/abstained/preview를 빠짐없이 남기고 평균에 성공만 몰래 남기지 않는다. config 비교는 청킹/모델/top_k/예산 변경 가능하지만 보고서에 바뀐 축을 표시하며 한 축씩 바꾸는 실습을 기본으로 안내한다. 같은 LLM 문맥 비교와 end-to-end 청킹 비교의 조건 차이를 설명한다.

생성 요청 최대 questions*configs(80회), retry0, explicit execute만. 이번 실제 검증에서는 외부 생성0회이며 자동 live sweep은 금지다. 실제 사용 시 호출 수·선택 provider/모델과 문서 전송 범위를 preview summary로 확인할 수 있다. API 금액은 가격 설정이 없으므로 null/unmeasured, usage null은0이 아니다. provider query-time 지연과 전체 파싱/청킹/검색 지연을 구분한다.

run에는 source/chunk/index/config/query/messages hashes, candidate/전달/excluded ID, effective settings, provider/model identity·status/usage, stage latency, citation validation, `execution_kind`(preview/live/test_fixture)를 기록한다. injected transport를 쓰면 자동 test_fixture이며 live로 표시할 수 없다. 테스트 응답을 production 기본값/실모델 품질로 사용하지 않는다. Faithfulness/Correctness/Recall/MRR/nDCG는 아직 evaluator/qrels를 연결하지 않아 null과 reason=evaluator_not_connected 또는 ground_truth_not_configured다. P013과 승인된 데이터는 재사용 연결 예정이지 이번에 호출하지 않는다.

## 검증과 완료

- 합성 TXT/Markdown 다중 문서, 실제 기존 가상 PDF를 입력받아 snapshot→build→ask/compare까지 검증. 개인 문서나 실제 키는 사용하지 않는다. 기존 parser6.21.2를 사용한 PDF 페이지/원문 인용을 확인한다.
- 별도 수기 fixture: 두 대상 요건과 서로 다른 페이지·문서의 근거, long section 2만자 이상, overlap0/경계, 비ASCII/NFC/CRLF, exact slice/coverage/maximum, heading path, 동일설정 fingerprint·LLM만 변경시 identity불변.
- 독립 BM25 기대 순위/동점/빈질문, top-k와 예산 누락, no-context/no-key/no-network, stale snapshot/index/hash/path/unknown option, duplicate ID, 미지원/암호/손상/빈/스캔PDF·timeout·oversize.
- 세 P025 provider의 fake transport로 wire→업무 JSON→원문 citation E2E, 전달되지 않은 ID/중복·추가필드·모델 실패/절단/부정확 JSON. actual default는 P025 실transport이고 tests만 injection한다.
- compare는 질문별 모든 row·동일 source·변경축·실패·N/A/비용null·fixture 라벨을 검증. 기존 output no-clobber, 파일 변조와 source 변경으로 stale, private output Git 제외.
- 기존 Naive/Chunking/evaluation/locks/artifacts/P013 상태·GT·grant hash 보존, P025 회귀. 테스트 환경은 설치된 Python3.12.14이며 새 모델/API/다운로드0회. loopback fake server만 허용하고 외부 socket/DNS 차단.

증거 docs/verification/p026/. 가이드에 실제 되는 옵션과 아직 안 되는 옵션, Python/선택 PDF 의존성, 재현 명령·프리뷰/실행 차이·N/A·오류 복구를 명시한다. 실제 모델/한국어 품질/메모리/새컴퓨터 설치/UI 통합을 완료라고 주장하지 않는다. C1~C3가 전체 위 범위를 포함하며 정확 채택·코드/검증·정상 personal/dev push까지 기록한다.
