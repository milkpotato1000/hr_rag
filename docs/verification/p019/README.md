# P019 — evaluator preparation and human review packet

The exact plan `e065560e3a48a6a4a1d41c26a721ee2a99521dce` was adopted on dev.
This completes preparation evidence, **not human approval or P013 readiness**.

## Review deliverables

- Read `evaluation/project_b/preparation/artifacts/run001/review.html`.
- Machine packet: adjacent `packet.json`; file hashes: `packet-manifest.json`.
- Packet canonical JSON SHA-256: `6f9b0b673b4b18e3739ac5038f048c00c8563ceaeab9dde105dedea9b1e13508`.
- Ten questions: eight source-backed model drafts with Codex revisions (48 final
  standalone claims), plus two document-limited amount-absence candidates.
- Eighteen controlled synthetic E/N/C proposals, six types × three labels.
- Every question/label remains draft or needs_revision, reviewer Codex,
  human_approval null. Previous Codex versions, model originals, source excerpts,
  page/Unicode offsets, exact quote hashes, and revision differences are retained.
- The report panel was requested through the app; the host returned queued.
  The actual HTML file is available independently of panel focus.

## Actual model and resource evidence

Pinned qwen3:8b Q4_K_M manifest/layer match P019. The official license is Apache-2.0.
`model-lock.json`, actual tokenizer/template metadata and byte-alphabet checks
record provenance. Only the local modelfile absolute cache path is redacted in
`model-show.json.gz` (lossless gzip; archive hashes recorded); its original field hash is retained. The template, tokenizer,
parameters, license and model-info hashes are preserved.

Download: 5,225,388,164 blob bytes, 90.26 seconds across two attempts. The first
attempt downloaded verified blobs but assumed the server used the home cache.
The running server uses its existing ignored runtime cache. The second attempt
reused external verified weights through links and downloaded **zero blob bytes**.
No weights were copied into Git, existing model deleted, or server restarted.
Metadata/manifest traffic is separate from the recorded blob count and remains
well within the 6 GiB total allowance. Start disk free was over 12 GiB.

Actual run: **30/34 calls**, 1,287.99/2,700 model wall seconds, max 103.23/120 seconds
per call. Categories: 8 smoke attempts, 6 repeat calls, 16 question-draft attempts.
All requests use context8192/output1024, temperature0/seed42, think=false,
stream=false, keep_alive=0. Full source spans are preserved. Revised payload
maximum conservative byte/token upper bound is **7,310 ≤ 8,192**. Actual model
metadata context40960 is not confused with the request context8192.

Physical RAM: 17,179,869,184 bytes (16 GiB). Maximum sampled sum of Ollama process
RSS: 6,735,839,232 bytes (~6.27 GiB), sampled each second. This is not a guaranteed
true peak, isolated GPU usage, or total machine usage. Runtime-final confirms no
loaded model after keep_alive=0 and preserves original 4B/BGE model digests.

## Quality findings — failures are part of the result

- Original first-attempt smoke: 5/6 pass. The ground-answer smoke copied the
  question into answer twice; claims did not match that answer.
- One frozen ground-v2 instruction clarification retained the same question,
  source and schema. Final six role smokes and six same-payload repeats pass;
  repeated normalized JSON outputs agree 6/6. Counters were never reset.
- Across 30 calls, 28 match JSON schema and 12 pass exact quote checks. These are
  different checks; neither is a general Korean HR evaluator accuracy estimate.
- **0/8 real-question cases passed strict exact-quote validation.** PDF line-break
  normalization, repeated/modified quotes and missing answer conditions occur.
  gt01 omits probation exclusion. gt08 reaches the fixed 1024-token output limit
  and produces partial JSON on both attempts. All raw replies/errors/usage remain.
- Codex corrections are source-backed proposals, not a substitute model success.
  Short context-dependent fragments were revised to name the policy and necessary
  conditions. Incident recording fields were merged into one meaningful claim;
  all questions remain within eight reference claims.
- Amount-absence review scans the entire 38,582-character canonical and complete
  policy inventory, retaining matching contexts and limits. It does not assert
  that the real company offers no such benefit and invents no absence span.

## Verification and preservation

17 standard-library tests pass: hash/truncation, ID/quote/offset, schema, limits,
partial output, timeout/no-next-call, pending restart, duplicate ledger records,
artifact tamper, retry/category caps, cumulative prompt revision, approval refusal,
parameter-order handling, and JSON/report roundtrip. Mock tests are clearly
separate from the 30 actual model calls.

Standalone copy verify → report → verify passes without any model request,
product module, original repository, or cache. The HTML hash is identical after
replay (`standalone.json`). Source/PDF and selected P007 baseline/candidate
manifests and BM25/Dense index fingerprints were read/verified, never re-ranked or
used as model answer inputs. Original tracked files, P007/P017 product results,
existing model budget ledger and four dirty plan files retain their hashes.

`p013-handoff.json` contains frozen inputs, lock/schema/ledger/report hashes and
remaining human decisions. P013 scoring, P008 UI and NLI are not implemented.
P013 must separately review human responses and the model's provenance/output
limitations before readiness. P019 does not create any human approval action.

Whitespace checks exclude only the exact canonical text snapshot and generated HTML
that displays its exact quotes; PDF-extracted trailing spaces are deliberately
preserved. All source code and other staged files pass the normal whitespace check.
