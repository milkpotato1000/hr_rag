"""Independent source/offset/publication boundary tests; no network or live LLM."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import document_common as common
import snapshot_drive_fixture as drive
import ingest_documents as ingest
import chunk_documents as chunks
import prepare_source_evaluation as evaluation
import rag
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject, NumberObject

ROOT = common.STAGE / 'data/source-v2'


def pdf_fixture(path, types=('text',), encrypted=False):
    writer = PdfWriter()
    for kind in types:
        page = writer.add_blank_page(width=300, height=300)
        if kind == 'text':
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
                                     NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            stream = DecodedStreamObject(); stream.set_data(b'BT /F1 12 Tf 20 250 Td (Independent PDF text 123) Tj ET')
            page[NameObject('/Contents')] = writer._add_object(stream)
        elif kind == 'image':
            image = DecodedStreamObject(); image.set_data(b'\xff\x00\x00')
            image.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                          NameObject('/Width'): NumberObject(1), NameObject('/Height'): NumberObject(1),
                          NameObject('/ColorSpace'): NameObject('/DeviceRGB'), NameObject('/BitsPerComponent'): NumberObject(8)})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/XObject'): DictionaryObject({NameObject('/I'): writer._add_object(image)})})
            stream = DecodedStreamObject(); stream.set_data(b'q 100 0 0 100 20 20 cm /I Do Q')
            page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('fixture-password')
    writer.write(path)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def catalog(self, text='가나다라마바사아자차', fmt='txt', pdf_types=('text',), encrypted=False):
        source = self.root / ('source.' + fmt)
        if fmt == 'pdf':
            pdf_fixture(source, pdf_types, encrypted)
        else:
            source.write_bytes(text.encode())
        row = {'document_id': 'doc', 'version': '2', 'title': 'fixture title', 'format': fmt,
               'path': source.name, 'sha256': common.file_hash(source), 'synthetic': True, 'authored_by': 'test fixture',
               'file_id': 'fixture:one', 'name': source.name, 'source_modified_time': '2026-10-23T00:00:00Z',
               'source_version': None, 'source_url': None}
        value = {'source_provider': 'google_drive', 'source_mode': 'fixture', 'folder_id': 'fixture:folder',
                 'timestamps_synthetic': True, 'documents': [row]}
        path = self.root / 'catalog.json'; common.write_json(path, value)
        return path, value

    def extracted(self, text='가나다라마바사아자차', **kw):
        path, _ = self.catalog(text, **kw)
        drive.snapshot(path, self.root / 'snapshot')
        result = ingest.ingest(self.root / 'snapshot/manifest.json', self.root / 'extracted')
        return self.root / 'extracted/manifest.json', result

    def test_snapshot_byte_preservation_and_identity_changes(self):
        catalog, data = self.catalog()
        original = (self.root / 'source.txt').read_bytes()
        first = drive.snapshot(catalog, self.root / 's1')
        repeat = drive.snapshot(catalog, self.root / 's2')
        self.assertEqual(first, repeat)
        row = first['documents'][0]
        self.assertEqual((self.root / 's1' / row['path']).read_bytes(), original)
        data['documents'][0]['name'] = 'renamed.txt'; common.write_json(catalog, data)
        rename = drive.snapshot(catalog, self.root / 's3')
        self.assertEqual(rename['documents'][0]['file_id'], row['file_id'])
        self.assertEqual(rename['documents'][0]['sha256'], row['sha256'])
        self.assertNotEqual(rename['snapshot_id'], first['snapshot_id'])
        (self.root / 'source.txt').write_text('changed source')
        data['documents'][0]['sha256'] = common.file_hash(self.root / 'source.txt'); common.write_json(catalog, data)
        changed = drive.snapshot(catalog, self.root / 's4')
        self.assertNotEqual(changed['documents'][0]['sha256'], row['sha256'])
        self.assertNotEqual(changed['snapshot_id'], rename['snapshot_id'])
        data['documents'][0]['file_id'] = 'fixture:new-upload'; common.write_json(catalog, data)
        upload = drive.snapshot(catalog, self.root / 's5')
        self.assertNotEqual(upload['documents'][0]['file_id'], row['file_id'])
        self.assertNotEqual(upload['snapshot_id'], changed['snapshot_id'])

    def test_snapshot_rejects_escape_duplicates_bad_hash_and_nonfixture(self):
        path, good = self.catalog()
        for change in ('escape', 'duplicate', 'hash', 'real', 'url', 'duplicate_file'):
            value = copy.deepcopy(good)
            if change == 'escape': value['documents'][0]['path'] = '../source.txt'
            if change == 'duplicate': value['documents'].append(copy.deepcopy(value['documents'][0]))
            if change == 'hash': value['documents'][0]['sha256'] = '0' * 64
            if change == 'real': value['source_mode'] = 'live'
            if change == 'url': value['documents'][0]['source_url'] = 'https://drive.google.com/fake'
            if change == 'duplicate_file':
                other = copy.deepcopy(value['documents'][0]); other['document_id'] = 'another'; value['documents'].append(other)
            common.write_json(path, value)
            with self.subTest(change=change), self.assertRaises((ValueError, OSError)):
                drive.snapshot(path, self.root / change)
            self.assertFalse((self.root / change).exists())
        link = self.root / 'external.txt'; link.symlink_to('/etc/hosts')
        with self.assertRaises(common.DocumentError): common.safe_file(self.root, link.name)

    def test_utf8_nfc_lf_and_exact_canonical_page_mapping(self):
        manifest_path, result = self.extracted('e\u0301\r\n한글\r끝\n')
        self.assertEqual(result['status'], 'complete')
        doc = result['documents'][0]
        canonical = (manifest_path.parent / doc['canonical_path']).read_text()
        self.assertEqual(canonical, 'é\n한글\n끝\n')
        self.assertEqual((doc['pages'][0]['start'], doc['pages'][0]['end']), (0, len(canonical)))
        self.assertEqual(chunks.load_documents(manifest_path)[1][0][1], canonical)
        # The cache is immutable and retained, including CRLF bytes.
        source = self.root / 'snapshot' / doc['original_path']
        self.assertIn(b'\r\n', source.read_bytes())
        self.assertIn(b'\r\n', (manifest_path.parent / doc['pages'][0]['raw_text_path']).read_bytes())

    def test_real_pypdf_page_count_and_boundary_mapping(self):
        manifest_path, result = self.extracted(fmt='pdf', pdf_types=('text', 'text'))
        self.assertEqual(len(result['documents'][0]['pages']), 2)
        pages = result['documents'][0]['pages']
        a, b = pages[0]['end'] - 3, pages[1]['start'] + 4
        intersections = chunks.page_intersections(pages, a, b)
        self.assertEqual([x['page_number'] for x in intersections], [1, 2])
        self.assertEqual([(x['page_start'], x['page_end']) for x in intersections],
                         [(pages[0]['end'] - 3, pages[0]['end']), (0, 4)])
        self.assertEqual(pages[1]['start'] - pages[0]['end'], 2)
        self.assertEqual(chunks.load_documents(manifest_path)[1][0][1].count('Independent PDF text 123'), 2)

    def test_blank_and_image_pages_are_review_only_not_complete(self):
        _, result = self.extracted(fmt='pdf', pdf_types=('text', 'blank', 'image'))
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual([x['classification'] for x in result['review_pages']], ['blank_candidate', 'ocr_candidate'])
        self.assertFalse((self.root / 'extracted/manifest.json').exists())
        self.assertTrue((self.root / 'extracted/review.json').exists())
        with self.assertRaises(common.DocumentError):
            chunks.chunk(self.root / 'extracted/review.json', self.root / 'chunks')
        self.assertFalse((self.root / 'chunks').exists())

    def test_empty_markdown_requires_review(self):
        _, result = self.extracted(' \n\t')
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(result['review_pages'][0]['classification'], 'blank_candidate')

    def test_damaged_and_encrypted_pdf_are_explicit_errors(self):
        source = self.root / 'bad.pdf'; source.write_bytes(b'%PDF-1.7\nbroken')
        with self.assertRaises(common.DocumentError) as context:
            ingest.pdf_pages(source, 10)
        self.assertEqual(context.exception.kind, 'damaged_pdf')
        pdf_fixture(source, encrypted=True)
        with self.assertRaises(common.DocumentError) as context:
            ingest.pdf_pages(source, 10)
        self.assertEqual(context.exception.kind, 'encrypted_pdf')

    def test_timeout_worker_is_killed_and_does_not_publish(self):
        catalog, _ = self.catalog(fmt='pdf')
        drive.snapshot(catalog, self.root / 'snapshot')
        with self.assertRaises(common.DocumentError) as context:
            ingest.ingest(self.root / 'snapshot/manifest.json', self.root / 'output', pdf_timeout_seconds=0.000001)
        self.assertEqual(context.exception.kind, 'pdf_timeout')
        self.assertFalse((self.root / 'output').exists())
        self.assertFalse(list(self.root.glob('.document-stage-*')))

    def test_limits_unsupported_formats_and_missing_pages(self):
        path, data = self.catalog()
        with patch.object(common, 'MAX_BYTES', 2), self.assertRaises(common.DocumentError):
            drive.snapshot(path, self.root / 'big')
        data['documents'][0]['format'] = 'docx'; common.write_json(path, data)
        with self.assertRaises(common.DocumentError): drive.snapshot(path, self.root / 'unsupported')
        source = self.root / '101.pdf'; pdf_fixture(source, ('blank',) * 101)
        with self.assertRaises(common.DocumentError) as context: ingest.pdf_pages(source, 10)
        self.assertEqual(context.exception.kind, 'page_limit')
        response = {'status': 'ok', 'parser': {}, 'pages': [{'page_number': 2, 'text': 'lost first'}]}
        with patch.object(ingest.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(response), '')):
            with self.assertRaises(common.DocumentError) as context: ingest.pdf_pages(source, 10)
        self.assertEqual(context.exception.kind, 'missing_page')

    def test_tampered_cache_and_invalid_utf8_fail_without_output(self):
        path, _ = self.catalog()
        manifest = drive.snapshot(path, self.root / 'snapshot')
        cached = self.root / 'snapshot' / manifest['documents'][0]['path']
        cached.write_text('tampered')
        with self.assertRaises(common.DocumentError) as context:
            ingest.ingest(self.root / 'snapshot/manifest.json', self.root / 'output')
        self.assertEqual(context.exception.kind, 'hash_mismatch')
        self.assertFalse((self.root / 'output').exists())
        source = self.root / 'source.txt'; source.write_bytes(b'\xff')
        data = common.read_json(path); data['documents'][0]['sha256'] = common.file_hash(source); common.write_json(path, data)
        drive.snapshot(path, self.root / 's2')
        with self.assertRaises(common.DocumentError) as context:
            ingest.ingest(self.root / 's2/manifest.json', self.root / 'bad-utf8')
        self.assertEqual(context.exception.kind, 'invalid_utf8')
        self.assertFalse((self.root / 'bad-utf8').exists())

    def test_atomic_visibility_exception_existing_and_racing_destination(self):
        target = self.root / 'output'
        with common.atomic_directory(target) as stage:
            (stage / 'data').write_text('whole')
            self.assertFalse(target.exists())
        self.assertEqual((target / 'data').read_text(), 'whole')
        with self.assertRaises(common.DocumentError):
            with common.atomic_directory(target): pass
        with self.assertRaises(RuntimeError):
            with common.atomic_directory(self.root / 'fail') as stage:
                (stage / 'manifest.json').write_text('partial')
                raise RuntimeError('injected write failure')
        self.assertFalse((self.root / 'fail').exists())
        race = self.root / 'race'
        with self.assertRaises(OSError):
            with common.atomic_directory(race) as stage:
                (stage / 'data').write_text('must not replace')
                race.mkdir()
        self.assertEqual(list(race.iterdir()), [])
        link = self.root / 'dangling'; link.symlink_to(self.root / 'missing')
        with self.assertRaises(common.DocumentError):
            with common.atomic_directory(link): pass

    def test_independent_windows_boundaries_overlap_and_no_duplicate_tail(self):
        self.assertEqual([(a, b, 'abcdefghij'[a:b]) for a, b in chunks.windows('abcdefghij', 4, 1)],
                         [(0, 4, 'abcd'), (3, 7, 'defg'), (6, 10, 'ghij')])
        self.assertEqual(list(chunks.windows('abcd', 4, 1)), [(0, 4)])
        self.assertEqual(list(chunks.windows('abcde', 4, 1)), [(0, 4), (3, 5)])
        self.assertEqual(list(chunks.windows('abcdefghi', 4, 0)), [(0, 4), (4, 8), (8, 9)])
        self.assertEqual(list(chunks.windows('abcdef', 4, 3)), [(0, 4), (1, 5), (2, 6)])
        self.assertEqual(list(chunks.windows('한글🙂e\u0301', 3, 0)), [(0, 3), (3, 5)])
        for size, overlap in [(True, 0), (0, 0), (4, -1), (4, 4), (4, True), ('4', 0), (4.0, 0)]:
            with self.subTest(size=size, overlap=overlap), self.assertRaises(common.DocumentError):
                list(chunks.windows('abc', size, overlap))
        for text in ['', ' \n', None]:
            with self.assertRaises(common.DocumentError): list(chunks.windows(text, 4, 0))

    def test_whitespace_skips_recorded_and_union_statistics_independent(self):
        source, _ = self.extracted('abcd    ij')
        report = chunks.chunk(source, self.root / 'out', size_chars=4, overlap_chars=0)
        source_map = common.read_json(self.root / 'out/source-map.json')
        self.assertEqual(source_map['skipped_windows'], [{'document_id': 'doc', 'start': 4, 'end': 8, 'reason': 'whitespace_only'}])
        self.assertEqual(report['statistics']['covered_unique_chars'], 6)
        self.assertEqual(report['statistics']['overlap_ratio'], 0)
        self.assertEqual(chunks.union_length([(0, 4), (3, 7), (6, 10)]), 10)

    def test_repeat_pipeline_stable_ids_hashes_run_id_and_configuration_change(self):
        source, first = self.extracted('abcdefghij')
        second = ingest.ingest(self.root / 'snapshot/manifest.json', self.root / 'extracted-again')
        self.assertEqual(first['run_id'], second['run_id'])
        a = chunks.chunk(source, self.root / 'c1', size_chars=4, overlap_chars=1)
        b = chunks.chunk(source, self.root / 'c2', size_chars=4, overlap_chars=1)
        c = chunks.chunk(self.root / 'extracted-again/manifest.json', self.root / 'c3', size_chars=4, overlap_chars=1)
        self.assertEqual(a['chunks_sha256'], b['chunks_sha256'])
        self.assertEqual(a['chunks_sha256'], c['chunks_sha256'])
        self.assertEqual(a['run_id'], b['run_id'])
        self.assertEqual(a['run_id'], c['run_id'])
        d = chunks.chunk(source, self.root / 'c4', size_chars=5, overlap_chars=1)
        self.assertNotEqual(a['run_id'], d['run_id'])
        self.assertNotEqual(a['chunks_sha256'], d['chunks_sha256'])
        for item, span in zip([json.loads(x) for x in (self.root / 'c1/chunks.jsonl').read_text().splitlines()],
                              common.read_json(self.root / 'c1/source-map.json')['chunks']):
            self.assertEqual(item['text'], 'abcdefghij'[span['start']:span['end']])
            self.assertEqual(span['provenance']['file_id'], 'fixture:one')
            self.assertNotIn('fixture title', item['text'])

    def test_offset_and_extraction_corruption_rejected(self):
        source, manifest = self.extracted()
        manifest['documents'][0]['pages'][0]['end'] += 1
        identity = {k: manifest[k] for k in ('schema_version', 'snapshot_manifest_sha256', 'normalization_version',
                                             'page_separator', 'ingestion_lock_sha256', 'documents')}
        manifest['run_id'] = common.fingerprint(identity); common.write_json(source, manifest)
        with self.assertRaises(common.DocumentError) as context:
            chunks.chunk(source, self.root / 'out')
        self.assertEqual(context.exception.kind, 'invalid_offset')
        self.assertFalse((self.root / 'out').exists())

    def test_explicit_cli_corpus_and_runtime_no_evaluation_files(self):
        path, _ = self.extracted('uniquelexeme only custom corpus')
        chunks.chunk(path, self.root / 'chunks')
        corpus = self.root / 'chunks/chunks.jsonl'
        process = subprocess.run([sys.executable, str(common.STAGE / 'scripts/ask.py'), '--question', 'uniquelexeme',
                  '--chunks', str(corpus), '--retriever', 'bm25', '--max-context-chars', '1'], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result['reason'], 'no_context')
        self.assertEqual(result['trace']['candidates'][0]['document_id'], 'doc')
        self.assertEqual(result['trace']['generation_calls'], 0)
        with patch.object(rag.evaluation, 'read_jsonl', wraps=rag.evaluation.read_jsonl) as reader:
            result = rag.ask('uniquelexeme', chunks_path=corpus, retriever='bm25', max_context_chars=1)
        self.assertEqual([Path(x.args[0]) for x in reader.call_args_list], [corpus])
        self.assertNotIn('required_fact', json.dumps(result))

    def test_prepared_original_spans_no_chunk_id_qrels_and_exact_pages(self):
        _, docs = chunks.load_documents(ROOT / 'extracted/manifest.json')
        value = common.read_json(ROOT / 'evaluation/source-evaluation.json')
        evaluation.validate_evaluation(value, docs)
        self.assertEqual(len(value['questions']), 14)
        self.assertEqual(sum(q['answerability'] == 'unanswerable' for q in value['questions']), 3)
        self.assertNotIn('relevance', json.dumps(value))
        self.assertNotIn('chunk_id', json.dumps(value))
        self.assertTrue(any(len(f['required_spans']) > 1 for f in value['facts']))
        damaged = copy.deepcopy(value); damaged['facts'][0]['required_spans'][0]['start'] += 1
        with self.assertRaises(common.DocumentError): evaluation.validate_evaluation(damaged, docs)
        damaged = copy.deepcopy(value); damaged['questions'][0]['required_fact_ids'] = ['not-a-fact']
        with self.assertRaises(common.DocumentError): evaluation.validate_evaluation(damaged, docs)

    def test_one_fact_can_require_spans_in_multiple_chunks(self):
        source, _ = self.extracted('abcdefghij')
        spec = {'facts': [{'fact_id': 'f', 'meaning': 'both distant pieces required', 'required_spans': [
                    {'document_id': 'doc', 'quote': 'ab'}, {'document_id': 'doc', 'quote': 'ij'}]}],
                'questions': [{'query_id': 'q', 'question': 'both?', 'answerability': 'answerable',
                               'required_fact_ids': ['f'], 'semantic_rubric': 'must contain both pieces'}]}
        common.write_json(self.root / 'spec.json', spec)
        value = evaluation.prepare(source, self.root / 'spec.json', self.root / 'eval')
        chunks.chunk(source, self.root / 'chunks', size_chars=4, overlap_chars=1)
        maps = common.read_json(self.root / 'chunks/source-map.json')['chunks']
        spans = value['facts'][0]['required_spans']
        self.assertEqual([(x['start'], x['end']) for x in spans], [(0, 2), (8, 10)])
        self.assertFalse(any(all(m['start'] <= x['start'] and m['end'] >= x['end'] for x in spans) for m in maps))
        self.assertTrue(all(any(m['start'] <= x['start'] and m['end'] >= x['end'] for m in maps) for x in spans))

    def test_canonical_limit_and_content_change_identity(self):
        catalog, data = self.catalog('abcdefghij')
        drive.snapshot(catalog, self.root / 'snapshot')
        with patch.object(ingest, 'MAX_CHARS', 4), self.assertRaises(common.DocumentError) as context:
            ingest.ingest(self.root / 'snapshot/manifest.json', self.root / 'too-long')
        self.assertEqual(context.exception.kind, 'text_limit')
        self.assertFalse((self.root / 'too-long').exists())
        ingest.ingest(self.root / 'snapshot/manifest.json', self.root / 'extracted')
        a = chunks.chunk(self.root / 'extracted/manifest.json', self.root / 'a', size_chars=4, overlap_chars=1)
        (self.root / 'source.txt').write_text('abcdXfghij')
        data['documents'][0]['sha256'] = common.file_hash(self.root / 'source.txt')
        common.write_json(catalog, data)
        drive.snapshot(catalog, self.root / 'snapshot2')
        ingest.ingest(self.root / 'snapshot2/manifest.json', self.root / 'extracted2')
        b = chunks.chunk(self.root / 'extracted2/manifest.json', self.root / 'b', size_chars=4, overlap_chars=1)
        self.assertNotEqual(a['run_id'], b['run_id'])
        self.assertNotEqual(a['chunks_sha256'], b['chunks_sha256'])
        ids = lambda path: {json.loads(line)['chunk_id'] for line in path.read_text().splitlines()}
        self.assertFalse(ids(self.root / 'a/chunks.jsonl') & ids(self.root / 'b/chunks.jsonl'))

    def test_source_quote_location_requires_unique_exact_nonwhitespace_content(self):
        self.assertEqual(evaluation.locate('기한은 3월\n31일이다.', '3월 31일이다.'), (4, 13))
        with self.assertRaises(common.DocumentError): evaluation.locate('abc abc', 'abc')
        with self.assertRaises(common.DocumentError): evaluation.locate('abc', 'absent')


if __name__ == '__main__':
    unittest.main()
