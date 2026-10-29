#!/usr/bin/env python3
"""Create six immutable source-v3 PDFs. ReportLab is an authoring-only dependency."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from document_common import STAGE, atomic_directory, read_json, write_json, file_hash, DocumentError, cli_error

ROOT = STAGE / 'data/source-v3'


def wrapped(text, size, width):
    line = ''
    for char in text:
        if line and pdfmetrics.stringWidth(line + char, 'HRKorean', size) > width:
            yield line
            line = ''
        line += char
    if line:
        yield line


def embedding_flags(font):
    data = font.read_bytes()
    count = struct.unpack_from('>H', data, 4)[0]
    for i in range(count):
        tag, _, offset, _ = struct.unpack_from('>4sIII', data, 12 + 16 * i)
        if tag == b'OS/2':
            return struct.unpack_from('>H', data, offset + 8)[0]
    return None  # Legacy macOS font has no OS/2 table; report absence, not permission.


def create(source, title, document_id, output):
    pdf = canvas.Canvas(str(output), pagesize=A4, invariant=1, pageCompression=1)
    pdf.setTitle(title + ' | fictional source v3')
    pdf.setAuthor('Codex - fictional learning fixture')
    width, height = A4
    y, page = height - 66, 1

    def footer():
        pdf.setStrokeColorRGB(.78, .83, .81)
        pdf.line(56, 48, width - 56, 48)
        pdf.setFillColorRGB(.35, .42, .40)
        pdf.setFont('Helvetica', 8)
        pdf.drawString(56, 32, document_id.upper() + ' / v3')
        pdf.drawRightString(width - 56, 32, str(page))

    def next_page():
        nonlocal y, page
        footer(); pdf.showPage(); page += 1; y = height - 66

    for block in source.read_text(encoding='utf-8').strip().split('\n\n'):
        if block == '<!-- pagebreak -->':
            next_page(); continue
        for paragraph in block.splitlines():
            title_line = paragraph.startswith('# ')
            heading = paragraph.startswith('## ')
            metadata = paragraph.startswith('문서 식별자:')
            warning = paragraph.startswith('가상 HR 규정')
            size = 22 if title_line else 12 if heading else 8.5 if metadata else 9 if warning else 11
            content = paragraph.lstrip('# ') if (title_line or heading) else paragraph
            lines = list(wrapped(content, size, width - 112))
            leading = size * 1.65
            # Keep a heading with the first body line; long body text may span pages.
            if y - len(lines) * leading - (30 if heading else 0) < 66:
                next_page()
            for line in lines:
                if y - leading < 60:
                    next_page()
                pdf.setFont('HRKorean', size)
                color = (.09,.27,.23) if (title_line or heading) else (.40,.45,.43) if (metadata or warning) else (.14,.18,.16)
                pdf.setFillColorRGB(*color)
                pdf.drawString(56, y, line)
                y -= leading
        y -= 10 if title_line else 7
    footer(); pdf.save()
    return page


def build(source_root, font, output_dir):
    lock = read_json(STAGE / 'authoring-lock.json')
    if reportlab.Version != lock['reportlab_version'] or file_hash(font) != lock['font_sha256']:
        raise DocumentError('dependency_mismatch', 'authoring reportlab/font differs from lock')
    flags = embedding_flags(font)
    if flags != lock['font_os2_fsType'] or (flags is not None and flags & (2 | 256 | 512)):
        raise DocumentError('font_permission', 'font does not permit required PDF subset embedding')
    metadata = read_json(source_root / 'document-metadata.json')['documents']
    names = [m['name'] for m in metadata]
    if sorted(names) != sorted(['birthday','annual','remote','welfare','training','travel']):
        raise DocumentError('missing_document', 'exactly six expected documents required')
    pdfmetrics.registerFont(TTFont('HRKorean', str(font)))
    record = {**lock, 'source_history':'Fictional source-v3 authoring; not real company originals',
              'font_note':'Local macOS authoring font; subset embedded, standalone font not redistributed. Other hosts use delivered PDFs or obtain licensed matching font.',
              'pdfs':[]}
    with atomic_directory(output_dir) as target:
        (target / 'pdf').mkdir()
        for m in metadata:
            original = source_root / 'authoring' / (m['name'] + '.md')
            path = target / 'pdf' / (m['name'] + '.pdf')
            pages = create(original, m['title'], m['document_id'], path)
            record['pdfs'].append({'document_id':m['document_id'],'path':'pdf/'+path.name,'pages':pages,
                                  'sha256':file_hash(path),'authoring_path':'authoring/'+original.name,
                                  'authoring_sha256':file_hash(original),'effective_date':None})
        write_json(target / 'pdf-authoring.json', record)
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--font',type=Path,required=True)
    p.add_argument('--source-root',type=Path,default=ROOT)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args()
    try:
        result=build(a.source_root,a.font,a.output_dir)
        print(json.dumps({'status':'complete','pdfs':len(result['pdfs']),'pages':sum(x['pages'] for x in result['pdfs'])}))
    except (OSError,ValueError,KeyError,TypeError) as exc:
        return cli_error(exc)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
