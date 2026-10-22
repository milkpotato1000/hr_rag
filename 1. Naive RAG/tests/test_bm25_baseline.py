"""Contract tests: independent scores, real CLI, and deterministic failure injection."""
import contextlib
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from unittest import mock

STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE / "scripts"))
import run_bm25_baseline as bm25


class BM25Tests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.directory = Path(self.scratch.name)
        self.output = self.directory / "result"
        self.chunks_path = self.directory / "chunks.jsonl"
        self.queries_path = self.directory / "queries.jsonl"
        self.chunks = [dict(chunk_id=cid, document_id="same-document", version="1", title=title,
                            text=text, source="synthetic://fixture/" + cid, synthetic=True)
                       for cid, title, text in [("a", "생일", "휴가"), ("b", "생일", "생일"), ("c", "연차", "안내")]]
        self.queries = [dict(query_id=qid, question=question, answerability=answerability, relevance=qrels)
                        for qid, question, answerability, qrels in [
                            ("q-repeat", "생일 생일", "answerable", {"a": 3, "b": 1}),
                            ("q-birthday", "생일", "answerable", {"a": 3, "b": 1}),
                            ("q-holiday", "휴가", "answerable", {"a": 3}),
                            ("q-oov", "미등록개념", "unanswerable", {}),
                            ("q-empty", "!!!", "unanswerable", {})]]
        self.write_inputs()

    def write(self, path, rows):
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    def write_inputs(self):
        self.write(self.chunks_path, self.chunks)
        self.write(self.queries_path, self.queries)

    def argv(self, output=None, options=None):
        return ["--chunks", str(self.chunks_path), "--queries", str(self.queries_path),
                "--output-dir", str(output or self.output)] + (options if options is not None else ["--top-k", "2", "--k", "1", "2"])

    def run_cli(self, output=None, options=None, seed="42"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        return subprocess.run([sys.executable, str(STAGE / "scripts/run_bm25_baseline.py")]
                              + self.argv(output, options), cwd=str(STAGE), env=env,
                              capture_output=True, text=True)

    def success(self, output=None, options=None, seed="42"):
        output = output or self.output
        result = self.run_cli(output, options, seed)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(set(p.name for p in output.iterdir()),
                         {"rankings.jsonl", "scores.jsonl", "metrics.json", "run.json"})
        return {name: json.loads((output / (name + ".json")).read_text()) for name in ("metrics", "run")}

    def rows(self, name="scores", output=None):
        return [json.loads(line) for line in ((output or self.output) / (name + ".jsonl")).read_text().splitlines()]

    def scores(self, output=None):
        return {row["query_id"]: row for row in self.rows(output=output)}

    def assert_score(self, actual, expected):
        self.assertLessEqual(abs(actual - expected), 1e-12)

    def rejection(self, options=None):
        sentinel = self.directory / "user-existing.txt"
        sentinel.write_bytes(b"preserve user bytes\x00\n")
        inputs = [p.read_bytes() for p in (self.chunks_path, self.queries_path)]
        result = self.run_cli(options=options)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error:", result.stderr)
        self.assertFalse(os.path.lexists(self.output))
        self.assertEqual(sentinel.read_bytes(), b"preserve user bytes\x00\n")
        self.assertEqual(inputs, [p.read_bytes() for p in (self.chunks_path, self.queries_path)])
        self.assertEqual(list(self.directory.glob(".bm25-*")), [])

    def test_independent_equal_length_scores_and_repeated_query(self):
        report = self.success()
        scores = self.scores()
        actual = scores["q-birthday"]["results"]
        self.assertEqual([row["chunk_id"] for row in actual], ["b", "a"])
        self.assert_score(actual[0]["score"], math.log(1.6) * 4.4 / 3.2)
        self.assert_score(actual[1]["score"], math.log(1.6))
        self.assertEqual(scores["q-repeat"]["results"], actual)
        holiday = scores["q-holiday"]["results"]
        self.assertEqual([row["chunk_id"] for row in holiday], ["a"])
        self.assert_score(holiday[0]["score"], math.log(8 / 3))
        self.assertEqual(report["run"]["statistics"], {"N": 3, "avgdl": 2.0})
        self.assertEqual(scores["q-oov"]["results"], [])
        self.assertEqual(scores["q-empty"]["query_tokens"], [])
        self.assertEqual(scores["q-empty"]["results"], [])

    def test_independent_length_normalization(self):
        self.chunks[1]["text"] = "생일 안내 안내"
        self.write_inputs()
        report = self.success()
        rows = self.scores()["q-birthday"]["results"]
        self.assertEqual([r["chunk_id"] for r in rows], ["b", "a"])
        self.assert_score(rows[0]["score"], math.log(1.6) * 4.4 / 3.65)
        self.assert_score(rows[1]["score"], math.log(1.6) * 2.2 / 1.975)
        self.assertEqual(report["run"]["statistics"]["avgdl"], 8 / 3)

    def test_normalization_casefold_digits_underscore_and_korean_particles(self):
        self.assertEqual(bm25.tokenize("생일 휴가 ＨＲ_2026!"), ["생일", "휴가", "hr", "2026"])
        self.chunks[0].update(title="ＨＲ_2026", text="휴가")
        self.chunks[1].update(title="휴가는", text="!!!")
        self.queries = [dict(query_id=qid, question=question, answerability="unanswerable", relevance={})
                        for qid, question in [("latin", "hr 2026"), ("base", "휴가"), ("particle", "휴가는"), ("empty", "_?!")]]
        self.write_inputs()
        self.success()
        scores = self.scores()
        self.assertEqual(scores["latin"]["query_tokens"], ["2026", "hr"])
        for qid, ids in [("latin", ["a"]), ("base", ["a"]), ("particle", ["b"]), ("empty", [])]:
            self.assertEqual([r["chunk_id"] for r in scores[qid]["results"]], ids)

    def test_tie_breaking_top_k_and_fewer_positive_results(self):
        self.chunks[1].update(title="!!!", text="!!!")
        self.chunks[2].update(title="생일", text="휴가")
        self.chunks.reverse()
        self.write_inputs()
        self.success()
        self.assertEqual([r["chunk_id"] for r in self.scores()["q-birthday"]["results"]], ["a", "c"])
        output = self.directory / "top-one"
        self.success(output, ["--top-k", "1", "--k", "1"])
        self.assertEqual([r["chunk_id"] for r in self.scores(output)["q-birthday"]["results"]], ["a"])

    def test_individual_and_all_empty_token_chunks(self):
        for row in self.chunks[1:]:
            row.update(title="!!!", text="___")
        self.write_inputs()
        report = self.success()
        self.assertEqual(report["run"]["statistics"], {"N": 3, "avgdl": 2 / 3})
        self.assert_score(self.scores()["q-birthday"]["results"][0]["score"], math.log(8 / 3) * 2.2 / 4)
        self.chunks[0].update(title="!!!", text="___")
        self.write_inputs()
        output = self.directory / "all-empty"
        report = self.success(output)
        self.assertEqual(report["run"]["statistics"], {"N": 3, "avgdl": 0})
        self.assertTrue(all(not row["results"] for row in self.rows(output=output)))

    def test_default_options(self):
        report = self.success(options=[])
        self.assertEqual(report["run"]["parameters"], {"k1": 1.2, "b": .75, "top_k": 20, "k": [5, 10, 20]})

    def test_qrels_and_answerability_do_not_affect_retrieval(self):
        before = self.success()
        self.queries[0].update(answerability="unanswerable", relevance={})
        self.queries[1]["relevance"] = {"c": 3}
        self.write_inputs()
        output = self.directory / "changed-labels"
        after = self.success(output)
        for name in ("rankings.jsonl", "scores.jsonl"):
            self.assertEqual((self.output / name).read_bytes(), (output / name).read_bytes())
        self.assertNotEqual(before["metrics"], after["metrics"])
        self.assertNotEqual(before["run"]["sha256"]["queries"], after["run"]["sha256"]["queries"])
        self.assertEqual(before["run"]["sha256"]["chunks"], after["run"]["sha256"]["chunks"])

    def test_only_title_text_and_question_affect_retrieval(self):
        self.success()
        for row in self.chunks:
            row.update(document_id="changed", version="2", source="synthetic://changed")
        self.write_inputs()
        other = self.directory / "changed-metadata"
        self.success(other)
        for name in ("rankings.jsonl", "scores.jsonl"):
            self.assertEqual((self.output / name).read_bytes(), (other / name).read_bytes())

    def test_real_p001_cli_reevaluation_matches_exactly(self):
        self.success()
        output = self.directory / "reevaluated.json"
        cmd = [sys.executable, str(STAGE / "scripts/evaluate_retrieval.py"), "--chunks", str(self.chunks_path),
               "--queries", str(self.queries_path), "--rankings", str(self.output / "rankings.jsonl"),
               "--k", "1", "2", "--output", str(output)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_bytes(), (self.output / "metrics.json").read_bytes())

    def test_metadata_hashes_schema_and_nonnegative_timings(self):
        report = self.success()
        run = report["run"]
        self.assertEqual(run["retriever_version"], "1.0.0")
        self.assertEqual(run["tokenizer"], {"id": "unicode-word-v1", "steps": ["NFKC", "casefold", "re.findall"], "pattern": r"[^\W_]+"})
        self.assertEqual(run["environment"], {"python_version": platform.python_version(),
                         "unicode_version": unicodedata.unidata_version, "platform": platform.platform()})
        for name, path in [("chunks", self.chunks_path), ("queries", self.queries_path), ("rankings", self.output / "rankings.jsonl")]:
            self.assertEqual(run["sha256"][name], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(run["sha256"], report["metrics"]["metadata"]["sha256"])
        self.assertEqual(set(run["observations"]["query_search_ms"]), {q["query_id"] for q in self.queries})
        timings = [run["observations"]["index_build_ms"]] + list(run["observations"]["query_search_ms"].values())
        self.assertTrue(all(math.isfinite(t) and t >= 0 for t in timings))
        rankings, scores = self.rows("rankings"), self.rows("scores")
        self.assertEqual([r["query_id"] for r in rankings], sorted(q["query_id"] for q in self.queries))
        for ranking, score in zip(rankings, scores):
            self.assertEqual(set(ranking), {"query_id", "chunk_ids"})
            self.assertEqual(set(score), {"query_id", "query_tokens", "results"})
            self.assertEqual(ranking["query_id"], score["query_id"])
            self.assertEqual(ranking["chunk_ids"], [r["chunk_id"] for r in score["results"]])
            self.assertTrue(all(set(r) == {"chunk_id", "score"} and math.isfinite(r["score"]) and r["score"] > 0 for r in score["results"]))

    def test_repeat_determinism_hash_seeds_and_input_order(self):
        before = self.success(seed="1")
        second = self.directory / "repeat"
        after = self.success(second, seed="999")
        for name in ("rankings.jsonl", "scores.jsonl", "metrics.json"):
            self.assertEqual((self.output / name).read_bytes(), (second / name).read_bytes())
        for run in (before["run"], after["run"]):
            run.pop("observations")
        self.assertEqual(before["run"], after["run"])
        self.chunks.reverse()
        self.queries.reverse()
        self.write_inputs()
        shuffled = self.directory / "shuffled"
        self.success(shuffled)
        for name in ("rankings.jsonl", "scores.jsonl"):
            self.assertEqual((self.output / name).read_bytes(), (shuffled / name).read_bytes())

    def test_bad_options_cli_and_boolean_library_boundary(self):
        for options in (["--top-k", "0"], ["--top-k", "-1"], ["--top-k", "1.2"],
                        ["--k", "0"], ["--k", "-1"], ["--k", "2", "2"], ["--k", "1.5"],
                        ["--k"], ["--top-k", "2", "--k", "3"]):
            with self.subTest(options=options):
                self.rejection(options)
        for top_k, ks in [(True, [1]), (2, [True]), (2, []), (2, "1"), (2, [1.0]), (2, [1, 1])]:
            with self.subTest(top_k=top_k, ks=ks), self.assertRaises(ValueError):
                bm25.run_baseline(self.chunks_path, self.queries_path, self.output, top_k, ks)
        index = bm25.BM25Index({r["chunk_id"]: r for r in self.chunks})
        with self.assertRaises(ValueError):
            index.search("생일", True)

    def test_invalid_inputs_reuse_p001_validation_without_publishing(self):
        for target in ("chunks", "queries"):
            for raw in ("", "{broken}\n", "[]\n", '{"x":NaN}\n'):
                with self.subTest(target=target, raw=raw):
                    self.write_inputs()
                    getattr(self, target + "_path").write_text(raw)
                    self.rejection()
        variants = [([self.chunks[0], self.chunks[0]], self.queries),
                    (self.chunks, [self.queries[0], self.queries[0]]),
                    (self.chunks, [dict(query_id="q", question="질문", answerability="answerable", relevance={"missing": 3})]),
                    (self.chunks, [dict(query_id="q", question="질문", answerability="answerable", relevance={"a": True})]),
                    (self.chunks, [dict(query_id="q", question="질문", answerability="unanswerable", relevance={"a": 0})])]
        for field, value in [("title", []), ("text", ""), ("synthetic", 1), ("source", "https://example.com")]:
            changed = copy.deepcopy(self.chunks)
            changed[0][field] = value
            variants.append((changed, self.queries))
        for chunks, queries in variants:
            with self.subTest(chunks=chunks, queries=queries):
                self.write(self.chunks_path, chunks)
                self.write(self.queries_path, queries)
                self.rejection()

    def test_existing_output_file_directory_and_links_are_preserved(self):
        target = self.directory / "user.txt"
        target.write_bytes(b"user file")
        candidates = [target, self.directory / "existing-dir", self.directory / "link", self.directory / "dangling"]
        candidates[1].mkdir()
        (candidates[1] / "user.txt").write_bytes(b"user directory")
        candidates[2].symlink_to(target)
        candidates[3].symlink_to(self.directory / "missing")
        for destination in candidates:
            with self.subTest(destination=destination):
                result = self.run_cli(destination)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("already exists", result.stderr)
                self.assertTrue(os.path.lexists(destination))
                self.assertEqual(target.read_bytes(), b"user file")
                self.assertEqual((candidates[1] / "user.txt").read_bytes(), b"user directory")
        self.assertTrue(candidates[3].is_symlink())
        self.assertEqual(list(self.directory.glob(".bm25-*")), [])

    def test_missing_input_or_output_parent(self):
        destination = self.directory / "no-parent" / "result"
        result = self.run_cli(destination)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("parent", result.stderr)
        self.assertFalse(destination.parent.exists())
        self.chunks_path.unlink()
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error:", result.stderr)
        self.assertFalse(self.output.exists())

    def assert_injected_failure(self, patcher):
        user = self.directory / "untouched-user-file"
        user.write_bytes(b"keep\x00")
        stderr = io.StringIO()
        with patcher, contextlib.redirect_stderr(stderr):
            code = bm25.main(self.argv())
        self.assertEqual(code, 2)
        self.assertIn("injected", stderr.getvalue())
        self.assertFalse(self.output.exists())
        self.assertEqual(user.read_bytes(), b"keep\x00")
        self.assertEqual(list(self.directory.glob(".bm25-*")), [])

    def test_injected_evaluation_and_staging_write_failures_cleanup(self):
        self.assert_injected_failure(mock.patch.object(bm25.evaluation, "evaluate", side_effect=ValueError("injected evaluation failure")))
        self.assert_injected_failure(mock.patch.object(bm25, "write_json", side_effect=OSError("injected staging write failure")))

    def test_injected_partial_publication_failure_rolls_back(self):
        original = bm25.shutil.copyfileobj
        calls = []
        def fail_second(source, target):
            calls.append(1)
            if len(calls) == 2:
                target.write(b"partial")
                raise OSError("injected publication failure")
            return original(source, target)
        self.assert_injected_failure(mock.patch.object(bm25.shutil, "copyfileobj", side_effect=fail_second))
        self.assertEqual(len(calls), 2)

    def test_output_created_after_preflight_is_preserved(self):
        original = bm25.publish_directory
        def concurrent_writer(staging, destination):
            destination.mkdir()
            (destination / "user.txt").write_bytes(b"another writer")
            original(staging, destination)
        stderr = io.StringIO()
        with mock.patch.object(bm25, "publish_directory", side_effect=concurrent_writer), contextlib.redirect_stderr(stderr):
            self.assertEqual(bm25.main(self.argv()), 2)
        self.assertIn("error:", stderr.getvalue())
        self.assertEqual((self.output / "user.txt").read_bytes(), b"another writer")
        self.assertEqual(set(p.name for p in self.output.iterdir()), {"user.txt"})
        self.assertEqual(list(self.directory.glob(".bm25-*")), [])


if __name__ == "__main__":
    unittest.main()
