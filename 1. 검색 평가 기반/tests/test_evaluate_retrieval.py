"""Black-box CLI tests; expected metrics do not call evaluator functions."""
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "evaluate_retrieval.py"


class RetrievalCLITests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.directory = Path(self.scratch.name)
        self.paths = {name: self.directory / (name + ".jsonl")
                      for name in ("chunks", "queries", "rankings")}
        self.output = self.directory / "report.json"
        self.chunks = [dict(chunk_id=cid, document_id="fictional-" + cid, version="1",
                            title="가상 규정", text="실제 정책이 아닌 테스트 문서",
                            source="synthetic://" + cid, synthetic=True)
                       for cid in ("a", "b", "x", "y", "z")]
        self.queries = [dict(query_id="q", question="가상 질문?", answerability="answerable",
                             relevance={"a": 3, "b": 1})]
        self.rankings = [dict(query_id="q", chunk_ids=["x", "b", "a"])]
        self.write_all()

    def write(self, name, rows):
        self.paths[name].write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                                          for row in rows), encoding="utf-8")

    def write_all(self):
        for name in self.paths:
            self.write(name, getattr(self, name))

    def run_cli(self, ks=(2, 5), output=None, paths=None):
        selected = paths or self.paths
        command = [sys.executable, str(CLI)]
        for name in ("chunks", "queries", "rankings"):
            command += ["--" + name, str(selected[name])]
        command += ["--k"] + [str(k) for k in ks]
        command += ["--output", str(output or self.output)]
        return subprocess.run(command, text=True, capture_output=True, cwd=str(ROOT))

    def success(self, ks=(2, 5)):
        process = self.run_cli(ks)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, "")
        return json.loads(self.output.read_text(encoding="utf-8"))

    def rejection(self, ks=(2, 5), expected=None):
        # Every invalid fixture must both preserve an existing output and leave no
        # new output when none existed. Compare bytes, not just parsed contents.
        sentinel = b"existing result\x00preserve exactly\n"
        self.output.write_bytes(sentinel)
        process = self.run_cli(ks)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("error:", process.stderr)
        if expected:
            self.assertIn(expected, process.stderr)
        self.assertEqual(self.output.read_bytes(), sentinel)
        self.output.unlink()
        process = self.run_cli(ks)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("error:", process.stderr)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.directory.glob(".retrieval-*.tmp")), [])

    def assert_metrics(self, actual, recall, precision, mrr, ndcg):
        self.assertEqual(set(actual), {"recall", "precision", "mrr", "ndcg"})
        for name, expected in zip(("recall", "precision", "mrr", "ndcg"),
                                  (recall, precision, mrr, ndcg)):
            self.assertAlmostEqual(actual[name], expected, places=12, msg=name)

    def test_contract_independent_graded_examples_and_macro(self):
        report = self.success()
        at_two = (1 / math.log2(3)) / (7 + 1 / math.log2(3))
        at_five = (1 / math.log2(3) + 7 / math.log2(4)) / (7 + 1 / math.log2(3))
        for metrics in (report["per_query"][0]["metrics"], report["macro"]):
            self.assert_metrics(metrics["2"], .5, .5, .5, at_two)
            self.assert_metrics(metrics["5"], 1, .4, .5, at_five)

    def test_relevant_first_kth_outside_k_empty_and_short(self):
        self.queries[0]["relevance"] = {"a": 3, "x": 0}
        cases = [(["a"], 1, .5, 1, 1),
                 (["x", "a"], 1, .5, .5, 1 / math.log2(3)),
                 (["x", "b", "a"], 0, 0, 0, 0),
                 ([], 0, 0, 0, 0),
                 (["x"], 0, 0, 0, 0)]
        for ranking, recall, precision, mrr, ndcg in cases:
            with self.subTest(ranking=ranking):
                self.rankings[0]["chunk_ids"] = ranking
                self.write_all()
                report = self.success((2,))
                self.assert_metrics(report["macro"]["2"], recall, precision, mrr, ndcg)

    def test_macro_is_query_mean_and_unanswerable_is_excluded(self):
        self.queries += [dict(query_id="empty", question="두 번째?", answerability="answerable",
                              relevance={"a": 1}),
                         dict(query_id="u1", question="근거 없음?", answerability="unanswerable", relevance={}),
                         dict(query_id="u2", question="근거 없음 둘?", answerability="unanswerable", relevance={})]
        self.rankings += [dict(query_id="empty", chunk_ids=[]), dict(query_id="u1", chunk_ids=["x"]),
                          dict(query_id="u2", chunk_ids=[])]
        self.write_all()
        report = self.success()
        self.assert_metrics(report["macro"]["2"], .25, .25, .25,
                            .5 * (1 / math.log2(3)) / (7 + 1 / math.log2(3)))
        self.assertEqual(report["metadata"]["answerable_count"], 2)
        self.assertEqual(report["metadata"]["unanswerable_count"], 2)
        self.assertEqual(report["unanswerable"], dict(query_count=2, with_results_count=1,
                         empty_results_count=1, with_results_ratio=.5, empty_results_ratio=.5))
        for row in report["per_query"][2:]:
            self.assertTrue(all(value is None for metric in row["metrics"].values() for value in metric.values()))

    def test_only_unanswerable_has_null_macro(self):
        self.queries[0].update(answerability="unanswerable", relevance={})
        self.write_all()
        report = self.success()
        self.assertEqual(report["metadata"]["answerable_count"], 0)
        self.assertTrue(all(value is None for metric in report["macro"].values() for value in metric.values()))
        self.assertEqual(report["unanswerable"]["with_results_ratio"], 1)

    def test_no_unanswerable_ratios_are_null(self):
        report = self.success()
        self.assertEqual(report["unanswerable"]["query_count"], 0)
        self.assertIsNone(report["unanswerable"]["with_results_ratio"])
        self.assertIsNone(report["unanswerable"]["empty_results_ratio"])

    def test_all_relevance_grades_and_large_k(self):
        self.queries[0]["relevance"] = {"a": 3, "b": 2, "x": 1, "y": 0}
        self.rankings[0]["chunk_ids"] = ["a", "b", "x", "y"]
        self.write_all()
        report = self.success((1, 3, 20))
        self.assert_metrics(report["macro"]["1"], 1 / 3, 1, 1, 1)
        self.assert_metrics(report["macro"]["3"], 1, 1, 1, 1)
        self.assert_metrics(report["macro"]["20"], 1, .15, 1, 1)

    def test_hashes_version_and_byte_determinism(self):
        report = self.success()
        first = self.output.read_bytes()
        for name, path in self.paths.items():
            self.assertEqual(report["metadata"]["sha256"][name], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(report["metadata"]["k"], [2, 5])
        self.assertEqual(report["metadata"]["evaluator_version"], "1.0.0")
        self.assertEqual(report["metadata"]["query_count"], 1)
        self.assertEqual(report["metadata"]["chunk_count"], 5)
        self.success()
        self.assertEqual(self.output.read_bytes(), first)
        self.chunks[0]["text"] += " 수정"
        self.write_all()
        changed = self.success()
        self.assertNotEqual(changed["metadata"]["sha256"]["chunks"], report["metadata"]["sha256"]["chunks"])
        self.assertEqual(changed["macro"], report["macro"])
        self.assertEqual(changed["per_query"], report["per_query"])
        self.write("chunks", self.chunks[1:])
        self.rejection(expected="unknown relevance chunk_id")

    def test_duplicate_record_ids(self):
        for name in self.paths:
            with self.subTest(name=name):
                self.write_all()
                rows = getattr(self, name)
                self.write(name, rows + [rows[0]])
                self.rejection(expected="duplicate")

    def test_malformed_and_empty_jsonl(self):
        for name in self.paths:
            for text in ("", " \n", "{broken}\n", "[]\n", "null\n", "42\n", "{}\n\n", '{"a":1,"a":2}\n', '{"x":NaN}\n'):
                with self.subTest(name=name, text=text):
                    self.write_all()
                    self.paths[name].write_text(text, encoding="utf-8")
                    self.rejection()
        self.write_all()
        self.paths["chunks"].write_bytes(b"\xff\xfe")
        self.rejection()

    def test_missing_and_invalid_chunk_fields(self):
        for field in self.chunks[0]:
            for value in (None, [], {}, 1, False, "", " "):
                with self.subTest(field=field, value=value):
                    self.write_all()
                    rows = copy.deepcopy(self.chunks)
                    rows[0][field] = value
                    self.write("chunks", rows)
                    self.rejection()
            with self.subTest(missing=field):
                self.write_all()
                rows = copy.deepcopy(self.chunks)
                del rows[0][field]
                self.write("chunks", rows)
                self.rejection()
        self.write_all()
        rows = copy.deepcopy(self.chunks)
        rows[0]["source"] = "https://example.com/real"
        self.write("chunks", rows)
        self.rejection(expected="synthetic://")

    def test_missing_and_invalid_query_fields(self):
        for field, values in {
            "query_id": [None, 1, [], "", " "],
            "question": [None, 1, [], "", " "],
            "answerability": [None, True, 1, [], {}, "unknown"],
            "relevance": [None, [], "a", True, 1, {}, {"a": 0}],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.write_all()
                    rows = copy.deepcopy(self.queries)
                    rows[0][field] = value
                    self.write("queries", rows)
                    self.rejection()
            with self.subTest(missing=field):
                self.write_all()
                rows = copy.deepcopy(self.queries)
                del rows[0][field]
                self.write("queries", rows)
                self.rejection()

    def test_invalid_grades_and_unknown_qrel_reference(self):
        for value in (True, False, -1, 4, 1.0, "1", None, [], {}):
            with self.subTest(value=value):
                self.write_all()
                rows = copy.deepcopy(self.queries)
                rows[0]["relevance"] = {"a": value}
                self.write("queries", rows)
                self.rejection(expected="grade")
        self.write_all()
        rows = copy.deepcopy(self.queries)
        rows[0]["relevance"] = {"missing": 0}
        self.write("queries", rows)
        self.rejection(expected="unknown relevance")

    def test_unanswerable_requires_empty_mapping_even_for_grade_zero(self):
        for relevance in ({"a": 3}, {"a": 0}):
            with self.subTest(relevance=relevance):
                self.queries[0].update(answerability="unanswerable", relevance=relevance)
                self.write_all()
                self.rejection(expected="must be empty")

    def test_missing_unknown_duplicate_and_invalid_rankings(self):
        bad_rows = [[], [dict(query_id="unknown", chunk_ids=[])],
                    [dict(query_id="q", chunk_ids=["a", "a"])],
                    [dict(query_id="q", chunk_ids=["missing"])],
                    [dict(query_id="q")], [dict(chunk_ids=[])]]
        bad_rows += [[dict(query_id="q", chunk_ids=v)] for v in (None, {}, "a", True, 1)]
        bad_rows += [[dict(query_id=v, chunk_ids=[])] for v in (None, [], {}, 1, " ")]
        bad_rows += [[dict(query_id="q", chunk_ids=[v])] for v in (None, [], {}, 1, True, " ")]
        for rows in bad_rows:
            with self.subTest(rows=rows):
                self.write_all()
                self.write("rankings", rows)
                self.rejection()
        self.queries.append(dict(query_id="missing-q", question="누락?", answerability="unanswerable", relevance={}))
        self.write_all()
        self.rejection(expected="missing ranking queries: missing-q")

    def test_k_must_be_positive_unique_integers(self):
        for ks in ((0,), (-1,), (2, 2), (1.5,), ("x",), ()):
            with self.subTest(ks=ks):
                self.rejection(ks)

    def test_input_read_error_preserves_output(self):
        self.paths["queries"].unlink()
        self.rejection()

    def test_output_cannot_alias_input_or_hardlink_or_symlink(self):
        for target in self.paths.values():
            before = target.read_bytes()
            process = self.run_cli(output=target)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("alias", process.stderr)
            self.assertEqual(target.read_bytes(), before)
        for kind in ("hardlink", "symlink"):
            alias = self.directory / kind
            if kind == "hardlink":
                import os
                os.link(str(self.paths["chunks"]), str(alias))
            else:
                alias.symlink_to(self.paths["chunks"])
            before = self.paths["chunks"].read_bytes()
            process = self.run_cli(output=alias)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn("alias", process.stderr)
            self.assertEqual(self.paths["chunks"].read_bytes(), before)

    def test_atomic_write_error_cleans_temporary_file(self):
        self.output.mkdir()
        marker = self.output / "preserve.txt"
        marker.write_text("preserve")
        process = self.run_cli()
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("error:", process.stderr)
        self.assertEqual(marker.read_text(), "preserve")
        self.assertEqual(list(self.directory.glob(".retrieval-*.tmp")), [])
        process = self.run_cli(output=self.directory / "absent" / "report.json")
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse((self.directory / "absent").exists())

    def test_synthetic_corpus_and_curated_example(self):
        source = ROOT / "data" / "synthetic"
        chunks = [json.loads(line) for line in (source / "chunks.jsonl").read_text().splitlines()]
        queries = [json.loads(line) for line in (source / "queries.jsonl").read_text().splitlines()]
        self.assertGreaterEqual(len(chunks), 12)
        self.assertGreaterEqual(len(queries), 10)
        self.assertEqual(len({c["chunk_id"] for c in chunks}), len(chunks))
        self.assertGreaterEqual(len({c["document_id"] for c in chunks}), 3)
        self.assertTrue(all(c["synthetic"] is True and "가상" in c["text"]
                            and c["source"].startswith("synthetic://") for c in chunks))
        ids = {c["chunk_id"] for c in chunks}
        self.assertTrue({"birthday-eligibility", "annual-accrual", "remote-eligibility", "welfare-birthday"} <= ids)
        self.assertGreaterEqual(sum(q["answerability"] == "unanswerable" for q in queries), 2)
        by_id = {q["query_id"]: q for q in queries}
        self.assertEqual(by_id["q03"]["relevance"]["birthday-eligibility"], 3)
        self.assertEqual(by_id["q03"]["relevance"]["birthday-window"], 3)
        self.assertEqual(by_id["q03"]["relevance"]["birthday-request"], 3)
        self.assertEqual(by_id["q01"]["relevance"]["welfare-birthday"], 0)
        process = self.run_cli((5, 10, 20), paths=dict(chunks=source / "chunks.jsonl",
                              queries=source / "queries.jsonl", rankings=source / "example_rankings.jsonl"))
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(self.output.read_text())
        self.assertEqual(report["metadata"]["answerable_count"], 11)
        self.assertEqual(report["metadata"]["unanswerable_count"], 3)
        self.assertAlmostEqual(report["macro"]["5"]["recall"], 10 / 11)
        self.assertAlmostEqual(report["macro"]["5"]["precision"], 17 / 55)
        self.assertAlmostEqual(report["macro"]["5"]["mrr"], 25 / 33)
        self.assertEqual(report["unanswerable"]["with_results_ratio"], 1 / 3)


if __name__ == "__main__":
    unittest.main()
