"""Regression for observed Ollama parameter-map ordering after restart."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import generation


class MetadataTests(unittest.TestCase):
    def test_order_only_change_accepted_without_lock_mutation(self):
        original={'name':'fixture','digest':'a'*64,'template':'same','parameters':'top_k 20\nstop "a"\nstop "b"\ntemperature 0.6'}
        changed={**original,'parameters':'temperature    0.6\nstop "b"\ntop_k 20\nstop "a"'}
        before=copy.deepcopy(original)
        self.assertEqual(generation.normalized_model(original),generation.normalized_model(changed))
        self.assertEqual(original,before)
        api=Mock();api.call.return_value={'version':'test'}
        g=generation.Generator(api=api,lock={'ollama_version':'test','model':original})
        with patch('generation.metadata',return_value=changed):g.check()

    def test_value_digest_template_and_duplicate_changes_rejected(self):
        original={'digest':'a'*64,'template':'same','parameters':'top_k 20\nstop "a"\nstop "b"'}
        api=Mock();api.call.return_value={'version':'test'}
        g=generation.Generator(api=api,lock={'ollama_version':'test','model':original})
        for update in [{'digest':'b'*64},{'template':'different'},{'parameters':'top_k 21\nstop "a"\nstop "b"'},
                       {'parameters':'top_k 20\nstop "a"'},{'parameters':'top_k 20\nstop "a"\nstop "b"\nstop "b"'}]:
            with patch('generation.metadata',return_value={**original,**update}),self.assertRaises(ValueError):g.check()
