# P013 recovery intake — runtime endpoint unavailable

2026-11-27. Exact READY d6cfda305dad37050750aaa5db4c5aecceeacdd1 adopted in ee6980c. Existing P013 execution logs and the completed first request remain intact.

Read-only GET requests to /api/version and /api/ps on http://127.0.0.1:11434 both returned connection refused (errno61). This establishes endpoint unavailability, not a missing installation or a model version mismatch. Runtime/model identity, loaded-model ownership and the 30-second preflight cannot currently be verified.

No inference/unload was attempted. No server start/restart, model download, recovery event, child experiment or new deadline was created. The single-use recovery grant has not been consumed. Parent manifest/ledger/call/cases/expectations hashes match the adopted recovery contract; parent pending=null/unresolved=true and the one completed call are preserved.

The user needs to restore the existing locked Ollama 0.40.8 endpoint at 127.0.0.1:11434. The recovery contract excludes agent server restarts. Once available, recheck the authorization and any newer stops, then implement/test/freeze the recovery runtime before executing the prescribed memory probe. No recovery implementation or new memory PASS is claimed by this intake record. P013 remains incomplete.
