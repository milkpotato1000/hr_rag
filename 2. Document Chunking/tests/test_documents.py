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
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject, NumberObject


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

    def test_blank_and_image_pages_are_review_only_not_complete(self):
        _, result = self.extracted(fmt='pdf', pdf_types=('text', 'blank', 'image'))
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual([x['classification'] for x in result['review_pages']], ['blank_candidate', 'ocr_candidate'])
        self.assertFalse((self.root / 'extracted/manifest.json').exists())
        self.assertTrue((self.root / 'extracted/review.json').exists())

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
