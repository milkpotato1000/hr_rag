#!/usr/bin/env python3
"""Rebuild two fictional source PDFs from new Markdown originals, using reportlab 4.4.9.
Authoring utility only; ingestion/runtime does not import reportlab or depend on a local font.
"""
import argparse
import hashlib
import json
from pathlib import Path
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

STAGE = Path(__file__).resolve().parents[1]
ROOT = STAGE / 'data/source-v2'


def wrapped(text, size, width):
    line = ''
    for char in text:
        if line and pdfmetrics.stringWidth(line + char, 'HRKorean', size) > width:
            yield line
            line = ''
        line += char
    if line:
        yield line


def create(name, font, output):
    pdfmetrics.registerFont(TTFont('HRKorean', str(font)))
    pdf = canvas.Canvas(str(output), pagesize=A4, invariant=1, pageCompression=1)
    pdf.setTitle('Fictional HR learning source v2 - ' + name)
    pdf.setAuthor('Codex - synthetic learning fixture, created 2026-10-23')
    width, height = A4
    y, page = height - 70, 1
    def footer():
        pdf.setFillColorRGB(.25, .32, .30)
        pdf.setFont('Helvetica', 8)
        pdf.drawString(48, 30, 'FICTIONAL HR / NEW SOURCE V2 / NOT COMPANY POLICY')
        pdf.drawRightString(width - 48, 30, str(page))
    for block in (ROOT / 'authoring' / (name + '.md')).read_text().strip().split('\n\n'):
        if block == '<!-- pagebreak -->':
            footer(); pdf.showPage(); page += 1; y = height - 70
            continue
        for paragraph in block.splitlines():
            heading = paragraph.startswith('#')
            size = 18 if paragraph.startswith('# ') else 13 if paragraph.startswith('## ') else 11
            content = paragraph.lstrip('# ') if heading else paragraph
            lines = list(wrapped(content, size, width - 96))
            if y - len(lines) * (size * 1.65) < 55:
                footer(); pdf.showPage(); page += 1; y = height - 70
            pdf.setFont('HRKorean', size)
            pdf.setFillColorRGB(.10, .26, .21) if heading else pdf.setFillColorRGB(.12, .15, .14)
            for line in lines:
                pdf.drawString(48, y, line)
                y -= size * 1.65
            if heading:
                y -= 4
        y -= 9
    footer(); pdf.save()
    return page


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / 'output/pdf'
    output.mkdir(parents=True, exist_ok=True)
    record = {'reportlab_version': reportlab.Version, 'font_name': args.font.name,
              'font_sha256': hashlib.sha256(args.font.read_bytes()).hexdigest(),
              'font_note': 'Local authoring font; embedded subset in PDF, font file not distributed.',
              'created_on': '2026-10-23', 'source_history': 'New fictional authoring, not recovered historical originals.', 'pdfs': []}
    for name in ('birthday', 'annual'):
        path = output / (name + '.pdf')
        if path.exists():
            raise ValueError('refuse to overwrite source PDF: ' + str(path))
        count = create(name, args.font, path)
        record['pdfs'].append({'path': path.relative_to(ROOT).as_posix(), 'pages': count,
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (ROOT / 'pdf-authoring.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    main()
