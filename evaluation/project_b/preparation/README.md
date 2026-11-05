# P019 evaluator preparation

## 최신 검토본: P022 / run003

[원자 주장 검토 보고서](artifacts/run003/review.html)는 **57개 미승인 후보**입니다.
run002의45개를 전수 검수해10개를 분리하고2개는 적용 조건을 복원했으며33개는 유지했습니다.
생일휴가의 재직 기간·대상자의 연간1일·수습 제외를 독립 주장으로 나눕니다. 동일한 원문
인용이 여러 독립 사실을 뒷받침할 수 있습니다. 반복한 대상/조건 자체를 추가 가산 사실로
세지 않습니다. 원자화 전후 분모가 달라 기존 점수를 같은 버전의 개선으로 비교할 수 없습니다.

각 질문의 새 주장 수는10,3,9,6,4,7,8,10,0,0개입니다. 구신ID/문장/사유/인용·조항·페이지·
위치·hash는 [개정 매핑](artifacts/run003/revision-mapping.json)에 있습니다. split 자식은
기존ID-a1/a2/a3, 유지/조건 복원은 기존ID입니다. 화면의 각 주장 상세에서도 이전 항목을
확인할 수 있습니다. 새 버전은 schema_version2 / p022-atomic-v1이며 과거 모델 max8
schema나 run001/run002는 바꾸지 않습니다. 새 작성 방법은 Codex의 원문 재검수이고
모델 호출은0회입니다. 과거 Qwen/Codex 이력·실패, 판정18개와 금액 미명시 후보는 보존합니다.

저장소 루트에서 생성하며, 이후 verify/report는 새 검토본 안에 동결된 감사 파일을 사용하므로
별도 plan 작업폴더가 필요 없습니다. preparation 전체와 세 run의 상대 위치를 함께 보존하세요.

```sh
python3 -B evaluation/project_b/preparation/prepare.py revise-atomic-review --parent evaluation/project_b/preparation/artifacts/run002 --audit docs/planning/reviews/p022/run002-atomicity-audit.json --out evaluation/project_b/preparation/artifacts/run003
python3 -B evaluation/project_b/preparation/prepare.py verify --out evaluation/project_b/preparation/artifacts/run003
python3 -B evaluation/project_b/preparation/prepare.py report --out evaluation/project_b/preparation/artifacts/run003
```

기존 출력의 변경·알 수 없는 버전·동결 제안이나 부모 손상·schema 불일치를 거부합니다.
run003에서 run/revise-ground는 모델 연결 전에 거부됩니다. 새 run003 자체의 실제
화면·좁은 폭·키보드 동작은2026-11-05 사용자가 직접 네 항목 모두 정상 확인했습니다.
근거는 docs/verification/p022/run003-user-ui-observation.json이며, Codex 도구 검증이나
정답 내용 승인으로 간주하지 않습니다. 이전 file URL 차단 증거는 보존합니다.

## 최신 검토본: P021 / run002

[새 검토 보고서](artifacts/run002/review.html)는 질문 → 정답 클레임 → 근거 원문
순서로 읽습니다. 각 주장의 인용은 펼쳐 두고 실험 로그·원응답·해시·문자 위치는
접힌 상세 정보로 분리했습니다. 로컬 HTML을 직접 열며 외부 서버/CDN이 필요 없습니다.
`gt`는 질문·정답 항목, `c`는 주장 ID이고 청크가 아닙니다. 원문 페이지는 PDF 페이지입니다.

48개 중 중복 조건을 정리해 **45개 미승인 주장**으로 개정했습니다. 생일휴가의
대상·연1일·수습 제외는 c02 하나에 통합하고, 교육휴가 대상은 기존 c02에 통합했습니다.
재택일 식대 미지원 문장의 반복 금액만 제거했습니다. 다른 주장과 판정 후보18개는
유지합니다. [개정 매핑](artifacts/run002/revision-mapping.json)에 기존48개 각각의
문장·ID·근거와 새45개 연결, 사유가 있습니다. ID는 재번호하지 않습니다.

run002는 모델 실험이 아니라 **run001의 오프라인 검토본 개정**입니다. 새로운 모델
호출은0회이고 원래 실행 기록30회와 구분합니다. [이전 보고서](artifacts/run001/review.html),
실패 기록 및 원문은 변경하지 않습니다. gt09/10은 문서에 금액이 없다는 확인 필요
후보이며 회사의 미지원으로 단정하지 않습니다. 어떤 후보도 사람 승인으로 승격하지 않습니다.

```sh
python3 -B prepare.py revise-review --parent artifacts/run001 --out artifacts/run002
python3 -B prepare.py verify --out artifacts/run002
python3 -B prepare.py report --out artifacts/run002
python3 -B -m unittest discover -s . -p 'test_*.py' -v
```

기존 run002가 있으면 검증만 하며 다른 내용으로 덮어쓰지 않습니다. 새 출력은
run001과 같은 부모 폴더의 새 경로에 생성합니다. 독립 복사 시 이 모듈과 run001을
함께 가져가세요. run002는 부모 패킷과 파일 hash를 검증합니다. 실행용 `.runner.lock`은
부모 이력의 일부가 아니므로 개정 패킷 hash에서 제외하되 원본 파일은 건드리지 않습니다.
`run`/`revise-ground`는 검토본에서 거부됩니다. 기존 run001 명령도 그대로 동작합니다.

P021의 실제 화면·좁은 폭·키보드 동작은2026-11-05 사용자 본인이 네 항목 모두
정상 확인했습니다. 관찰 출처는 docs/verification/p021/user-ui-observation.json입니다.
Codex의 브라우저 도구는 file URL 정책으로 차단됐으며 그 실패 이력을 보존합니다.
이 UI 확인은 정답 후보의 승인이나 새 run003의 화면 확인을 뜻하지 않습니다.

Small standard-library CLI for frozen local-model compatibility experiments and
an **unapproved** human review packet. No production scoring, serving, NLI model,
approval mutation, or integrated product UI is implemented here.

Run from this directory (or pass the script's path explicitly):

```sh
python3 -B prepare.py verify --out artifacts/run001
python3 -B prepare.py report --out artifacts/run001
python3 -B -m unittest discover -s . -p test_preparation.py -v
```

`verify` and `report` are offline. Copy this whole directory to another location
and use those commands to validate/replay the saved packet without a model call.
`report` never overwrites a different existing packet. Hashes use SHA-256 over
compact sorted-key UTF-8 JSON (`core.encoded`); source files and source quotes use
SHA-256 of their exact UTF-8 bytes. `packet-manifest.json` also identifies actual
JSON/HTML file-byte hashes. Quote offsets are canonical Unicode `[start,end)`.

The frozen run contains the complete source canonical, section/policy inventories,
source/PDF/selected P007 manifest hashes, actual raw model replies, cumulative
ledger, prompt revision, and original versus Codex source-checked drafts. It is
a small learning/development set, not an independent blind holdout.

## Model acquisition and execution

`acquire.py --evidence <folder> --server-cache <verified-running-server-path>`
is a network/cache mutation command, only for the explicitly approved P019 model.
Read the running server's `OLLAMA_MODELS` first. It pins official manifest and
blob hashes, downloads into the external home cache, and reuses verified blobs
through symlinks when the server cache differs. It never restarts the server,
deletes models, silently replaces tags, or copies weights into Git. A partial
download requires review; repeated full downloads are not automatic.

The actual installed byte-BPE vocabulary, template, and absence of a system
prompt must be reviewed before marking `single_user_template_verified` in a lock.
`freeze --repo <repo> --out <new-run> --model-lock <reviewed-lock>` verifies source
hashes and every full payload against the conservative byte bound. No truncation
or context enlargement is provided. Frozen inputs cannot be overwritten.

`run --out artifacts/run001` is the model-calling command. It uses only loopback
11434, 8B pinned digest, one user message, think/stream false, temperature 0,
seed 42, context 8192, output 1024, keep_alive 0, one call at a time. The shared
run ledger reserves before dispatch and includes failures: at most 34 requests,
120 seconds per request, and 2700 cumulative model wall seconds. A pending
reservation or ambiguous timeout blocks subsequent requests, including restart.
Actual local model calls are distinct from mocked unit tests.

`revise-ground` records the one bounded ground-v2 prompt clarification used in
this experiment. It preserves question/source/schema, freezes new payloads, and
registers the revision in the **existing cumulative ledger**. It does not erase
old failures, reset counters, or alter model/context limits. At most two attempts
per identical payload are allowed; repeats have one attempt. Six smoke successes
are repeated once with the same payload/settings, followed by eight draft cases.

## Interpretation

Schema success, exact quote validity, smoke semantic correctness, and general
answer quality are different. Numeric/negation/condition coverage in real draft
answers is reviewed by Codex against source and then left for human review.
The HTML shows raw replies and revisions; a valid JSON object is never a human
approval. The 18 E/N/C items are controlled synthetic proposals, not model-scored
or human-approved labels. Absence cases provide a whole-document/inventory audit
with its search limitations and no invented source span.

Memory evidence is sampled process RSS, not true peak physical/GPU memory. Smoke
success on six fixtures does not establish general Korean HR evaluator accuracy.
The existing 4B product, official chunking results, and their budget ledger remain
separate and unchanged. P013 still requires actual human review and readiness.
