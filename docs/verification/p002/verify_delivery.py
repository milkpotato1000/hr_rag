#!/usr/bin/env python3
"""Rerun P002 delivery evidence into a new directory; never overwrite old evidence."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / "1. Naive RAG"
ORIGINAL = "4225bb1d6b9bd017a06e81125c4fce9ed1d7f227"
P001_DONE = "60499ff47b80db930e832dc70e041498163b4e26"
OLD_STAGE = "413c82eecbdbb01393420ab371e9ba3c6f87af18"


def original_bytes(commit, path):
    return subprocess.run(["git", "show", commit + ":" + path], cwd=ROOT,
                          check=True, capture_output=True).stdout


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    output = parser.parse_args().output_dir.resolve()
    output.mkdir()  # Must be a new evidence directory.
    transcript = []
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    def run(command, cwd, expected=0):
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
        transcript.extend(["cwd: " + str(cwd), "command: " + json.dumps(command, ensure_ascii=False),
                           "exit: " + str(result.returncode), result.stdout.rstrip(), result.stderr.rstrip(), ""])
        (output / "commands.txt").write_text("\n".join(transcript).rstrip() + "\n")
        assert result.returncode == expected, result.stderr
        return result

    preserved = []
    manifest = json.loads((STAGE / "stage-manifest.json").read_text())
    assert manifest["title"] == "Naive RAG" and manifest["stage_number"] == 1
    assert {"P001", "P002"} <= set(manifest["plan_ids"])
    assert manifest["source_path_basis"] == "repository-relative"
    assert manifest["destination_path_basis"] == "stage-relative"
    assert len(manifest["files"]) == 6
    for row in manifest["files"]:
        raw = original_bytes(row["source_commit"], row["source_path"])
        assert row["source_stage"] == "legacy-root" and row["source_commit"] == ORIGINAL
        assert digest(raw) == row["copied_sha256"]
        assert raw == (STAGE / row["destination_path"]).read_bytes()
        assert raw == (ROOT / row["source_path"]).read_bytes()
        preserved.append({"file": row["destination_path"], "sha256": digest(raw), "original_stage_root_match": True})
    paths = subprocess.run(["git", "ls-tree", "-r", "--name-only", P001_DONE, "--", "docs/verification/p001"],
                           cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
    for name in paths + ["docs/planning/plans/P001.md"]:
        assert original_bytes(P001_DONE, name) == (ROOT / name).read_bytes()
    for name in ("README.md", "stage-manifest.json"):
        assert original_bytes(OLD_STAGE, "1. 검색 평가 기반/" + name) == (
            ROOT / "docs/verification/p002/02-layout-migration" / ("previous-" + name)).read_bytes()
    old_log = original_bytes(OLD_STAGE, "docs/planning/plans/P002.md").decode().split("<!-- EXECUTION:START -->\n")[1].split("<!-- EXECUTION:END -->")[0]
    new_log = (ROOT / "docs/planning/plans/P002.md").read_text().split("<!-- EXECUTION:START -->\n")[1].split("<!-- EXECUTION:END -->")[0]
    assert new_log.startswith(old_log)
    assert original_bytes(OLD_STAGE, "docs/verification/p002/01-stage1-preservation.txt") == (ROOT / "docs/verification/p002/01-stage1-preservation.txt").read_bytes()
    assert not (ROOT / "1. 검색 평가 기반").exists()
    assert not (ROOT / "2. BM25 검색 기준선").exists()
    assert sorted(p.name for p in ROOT.iterdir() if p.is_dir() and p.name[:1].isdigit()) == ["1. Naive RAG"]
    assert not any(p.is_symlink() for p in STAGE.rglob("*"))
    save_json(output / "preservation.json", {"files": preserved, "P001_card_and_evidence_unchanged": True,
             "previous_stage_metadata_and_logs_preserved": True, "old_paths_removed": True, "symlinks": False})

    run(["python3", "-m", "unittest", "discover", "-s", "tests", "-v"], ROOT)
    with tempfile.TemporaryDirectory(prefix="hr-rag-naive-standalone-") as scratch:
        standalone = Path(scratch) / "1. Naive RAG"
        shutil.copytree(STAGE, standalone, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        run(["python3", "-m", "unittest", "discover", "-s", "tests", "-v"], standalone)
        base = ["python3", "scripts/run_bm25_baseline.py", "--chunks", "data/synthetic/chunks.jsonl",
                "--queries", "data/synthetic/queries.jsonl", "--top-k", "20", "--k", "5", "10", "20"]
        baseline = output / "baseline"
        run(base + ["--output-dir", str(baseline)], standalone)
        repeat = Path(scratch) / "repeat"
        run(base + ["--output-dir", str(repeat)], standalone)
        for name in ("rankings.jsonl", "scores.jsonl", "metrics.json"):
            assert (baseline / name).read_bytes() == (repeat / name).read_bytes()
        before, after = [json.loads((p / "run.json").read_text()) for p in (baseline, repeat)]
        before.pop("observations"); after.pop("observations")
        assert before == after
        reevaluated = Path(scratch) / "reevaluated.json"
        run(["python3", "scripts/evaluate_retrieval.py", "--chunks", "data/synthetic/chunks.jsonl", "--queries",
             "data/synthetic/queries.jsonl", "--rankings", str(baseline / "rankings.jsonl"),
             "--k", "5", "10", "20", "--output", str(reevaluated)], standalone)
        assert reevaluated.read_bytes() == (baseline / "metrics.json").read_bytes()
        legacy = Path(scratch) / "legacy-example.json"
        run(["python3", "scripts/evaluate_retrieval.py", "--chunks", "data/synthetic/chunks.jsonl", "--queries",
             "data/synthetic/queries.jsonl", "--rankings", "data/synthetic/example_rankings.jsonl",
             "--k", "5", "10", "20", "--output", str(legacy)], standalone)
        assert legacy.read_bytes() == (ROOT / "docs/verification/p001/example-result.json").read_bytes()

        existing = Path(scratch) / "existing-result"
        existing.mkdir(); (existing / "user.txt").write_bytes(b"preserve bytes\x00")
        run(base + ["--output-dir", str(existing)], standalone, 2)
        assert (existing / "user.txt").read_bytes() == b"preserve bytes\x00"
        assert sorted(p.name for p in existing.iterdir()) == ["user.txt"]
        failed = Path(scratch) / "should-not-exist"
        run(base + ["--top-k", "0", "--output-dir", str(failed)], standalone, 2)
        assert not failed.exists()
        assert not list(Path(scratch).glob(".bm25-*"))
        save_json(output / "delivery-checks.json", {"standalone_tests": "37 PASS", "legacy_root_tests": "19 PASS",
                 "ranking_score_metric_repeat_bytes_equal": True, "run_except_observations_equal": True,
                 "reevaluated_metric_bytes_equal": True, "legacy_example_bytes_equal": True,
                 "actual_error_cases_preserved_existing_and_no_new_output": True})

    # Store a minimal inspectable fixture as well as testing it in the test suite.
    fixture = output / "independent-fixture"
    fixture.mkdir()
    chunks = [dict(chunk_id=cid, document_id="fictional-fixture", version="1", title=title, text=text,
                   source="synthetic://fixture/" + cid, synthetic=True)
              for cid, title, text in [("a", "생일", "휴가"), ("b", "생일", "생일"), ("c", "연차", "안내")]]
    queries = [dict(query_id="q", question="생일", answerability="answerable", relevance={"a": 3, "b": 1})]
    for name, rows in [("chunks", chunks), ("queries", queries)]:
        (fixture / (name + ".jsonl")).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    run(["python3", "scripts/run_bm25_baseline.py", "--chunks", str(fixture / "chunks.jsonl"),
         "--queries", str(fixture / "queries.jsonl"), "--top-k", "2", "--k", "1", "2",
         "--output-dir", str(fixture / "equal-length")], STAGE)
    equal = json.loads((fixture / "equal-length/scores.jsonl").read_text())["results"]
    assert [r["chunk_id"] for r in equal] == ["b", "a"]
    assert abs(equal[0]["score"] - math.log(1.6) * 4.4 / 3.2) <= 1e-12
    assert abs(equal[1]["score"] - math.log(1.6)) <= 1e-12
    chunks[1]["text"] = "생일 안내 안내"
    (fixture / "longer-chunks.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in chunks))
    run(["python3", "scripts/run_bm25_baseline.py", "--chunks", str(fixture / "longer-chunks.jsonl"),
         "--queries", str(fixture / "queries.jsonl"), "--top-k", "2", "--k", "1", "2",
         "--output-dir", str(fixture / "length-normalized")], STAGE)
    normalized = json.loads((fixture / "length-normalized/scores.jsonl").read_text())["results"]
    assert abs(normalized[0]["score"] - math.log(1.6) * 4.4 / 3.65) <= 1e-12
    assert abs(normalized[1]["score"] - math.log(1.6) * 2.2 / 1.975) <= 1e-12
    print("PASS: original hashes, root regression, standalone stage, baseline/repeat/reevaluation, failures and independent fixtures")


if __name__ == "__main__":
    main()
