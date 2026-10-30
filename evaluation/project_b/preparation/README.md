# P019 evaluator preparation

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
