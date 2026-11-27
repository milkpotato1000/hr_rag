# P010 오프라인 구현 검증

채택 plan `7ad76bdad4bd4c3aa2f08b9c5077d9e9b8bc4f5f`, adoption `e354abd`. 범용 package에 실제 HF worker, schema v2, cosine/RRF, immutable index, qrels와 CLI/UI를 연결했다. **사전학습 가중치 다운로드·로드, LLM/API/Drive/개인키 호출0**이다. P013 보류와 P029 C4 미완료는 그대로다.

## 검증 자료

- [SDK 선택](sdk-selection.json), [resolve 로그](resolve.log), [설치 로그](sdk-install.log), [정확 lock](../../../rag_package/requirements-retrieval.lock). 공식 PyPI Python3.12/macOS arm64 resolve/hash 기록 후 새 `.rag-runs/p010-sdk/.venv`에만 설치했다. 기존 의존성 lock/venv는 유지한다.
- [tiny SDK 결과](tiny-sdk.json), [코드](tiny_sdk.py), [로그](tiny-sdk.log). 10M parameters 미만·512MiB 미만의 로컬 무작위 Bert를 직접 생성하고 ST serialization→strict profile→실제 격리 worker→tokenization/encode를 확인했다. 384/1024차원, 직접 계산한 접두어·mean/CLS pooling·L2 값과 일치, 길이 초과 거부. 모델 이름은 catalog 계약 시험용이며 실제 pretrained E5/BGE 품질이 아니다. worker 종료와 ru_maxrss 관측을 기록한다.
- [회귀](regression-final.log), [검색 테스트](../../../tests/rag_package/test_hybrid.py). 수기 RRF/orthogonal·음수/cosine, zero/NaN/count/dim, flag, 두 모델, BM25 0embedding, vector bytes identity, outer reseal 변조, SDK mismatch, 문서 vector 재사용, qrels 분모/no-answer/불완전·실패/재생 일치, timeout/단일worker/UI registry/stale/쓰기 실패. 최종 69개 PASS, 기존 61개 포함.
- [최종 설치](installation.json), [빌드 명령](build-install-commands.json), [빌드 코드](build_install.py): allowlist→sdist→wheel→새 source-free venv. SDK와 PDF/Drive extras는 고정 hash lock만 설치했다. [core-only 새 환경](core-probe.json)에서도 기존 실습을 확인했다. 이전 설치 자료도 보존한다. 브라우저 설치본은 browser-installation.json에 따로 고정했고 최종본과 모든 UI 모듈/asset bytes가 같음을 확인했다. 최종 변경은 qrels 그룹 집계이며 독립 테스트·최종 설치 실습으로 확인했다.
- [독립 설치 실습](installed-probe.json), [코드](installed_probe.py), [로그](installed-probe.log): checkout 없는 cwd/PYTHONPATH unset에서 복사한 stage의 BM25/preview/명시 flag와 실제 SDK tiny worker build/query, generation0. 새 UI 설치의 [브라우저 관찰](browser-observations.json), [서버 종료](browser-server.json), [fixture](browser_fixture.py), [desktop](desktop-hybrid.jpg), [narrow](narrow-comparison.jpg).
- [보존·출처·링크 검사](checks.json), [변경 전 hash](preservation-before.json). 신규 stage는 P028 샘플만 선택 복사하고 provenance를 남겼다. 기존 HR LangChain/청킹/GT/평가·P013/P029 기록은 불변이다.

## 실패와 수정

`tiny-sdk-first.log`: 파일 경로 실행 시 package import 실패. module 실행으로 수정했다. `tiny-sdk-modules-failure.log`: SDK6의 정확 module type 이름 차이. 공식 설치물의 고정 built-in 이름만 whitelist에 추가했다. `tiny-sdk-pooling-failure.log`: 최신 pooling config가 boolean 대신 명시 mode를 저장함을 확인해 두 형식을 엄격 검증했다. custom code/pickle 허용으로 해결하지 않았다. 각 이전 로그와 수정 후 PASS를 보존했다.

`regression-first.log`: sandbox의 loopback bind 거부와 BM25 method 생략 호환 실패. 허용된 소유 fake 서버 시험으로 재실행하고 기존 기본 BM25 호출을 복구했다. `regression-loopback.log`는 호환 수정 전 실패, `regression-ui-path-failure.log`는 테스트 임시 경로의 `/var` symlink 거부이며 실제 resolved workspace fixture로 고쳤다. `hybrid-first.log`의 실행 flag 오류 우선순위를 수정하고 `hybrid-refined.log`를 남겼다.

계약 내 plan 검토에 따라 vectors hash를 실제 float32 bytes와 청크 순서 hash로 분리했고, 저장 문서/query SDK mismatch를 거부했다. 검색 지표는 answer 봉인 전에 기록해 compare 행과 result.json이 일치한다. 기존 artifact 덮어쓰기나 모델 재호출로 지표를 보충하지 않는다.

실제 브라우저는 새 IAB 탭에서 등록된 합성 문서만 사용했다. 기존 파일 선택창/앱 정책 거부를 재시도·우회하지 않았다. 최초 checkbox setChecked가 상태를 바꾸지 못해 DOM을 확인한 뒤 키보드 Space로 정상 선택했다. 새 검색 UI의 desktop/narrow/Tab/Enter/Space/원문/두 모델 비교를 관찰했으며 P029 C4 완료로 승계하지 않는다.

한계: 같은 Mac/Python3.12·CPU tiny model과 injected vectors만 검증했다. MPS·다른 OS·사전학습 한국어 품질/메모리·실제 답변·평가기·리랭커는 미검증/후속이다. 이번 구현 완료는 전체 제품 goal 완료가 아니다. SDK 출처와 모델 계약은 [ST API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html), [E5](https://huggingface.co/intfloat/multilingual-e5-small), [BGE-M3](https://huggingface.co/BAAI/bge-m3)를 확인했다.

최종 문구 수정: 비교 안내의 모델 호출 0회를 생성 LLM 요청 0회로 명확히 하고 체크한 임베딩 계산은 별도임을 표시했다. `core-verified-installation.json`의 실제 설치 검증본과 최종 wheel의 모든 core bytes가 같고, app.js는 이 한 문구 치환만 다름을 checks.json에서 확인했다. JS syntax PASS. 앞선 실제 browser 관찰을 보존하며 최종 문구를 별도로 재관찰했다고 주장하지 않는다.
