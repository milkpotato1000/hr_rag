"""Keep the installed example byte-identical to the original synthetic PDF."""
import hashlib
import json
from pathlib import Path
import unittest


class HandbookResourceTest(unittest.TestCase):
    def test_original_and_distributed_resource_match(self):
        root = Path(__file__).resolve().parents[2]
        resources = root / "rag_package/resources"
        manifest = json.loads((resources / "manifest.json").read_text())
        entry = next(row for row in manifest["files"] if row["path"] == "documents/handbook.pdf")
        original = root / "2. Document Chunking/data/source-v4/output/pdf/hr-handbook.pdf"
        self.assertEqual(original.read_bytes(), (resources / "sample" / entry["path"]).read_bytes())
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), entry["sha256"])
