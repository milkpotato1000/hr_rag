#!/usr/bin/env python3
"""Author one source-v4 handbook with natural pagination and a continuous footer."""
import argparse
from pathlib import Path
import reportlab
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from document_common import STAGE, read_json, write_json, file_hash, atomic_directory, cli_error
from handbook_model import parse, check_structure, require, DID
from create_source_pdfs import embedding_flags

def handbook_wrapped(text,size,width):
    lines=[];line=''
    for char in text:
        if line and pdfmetrics.stringWidth(line+char,'HRKorean',size)>width:
            tail=''
            if char in ".,!?)]}、。":
                token=line.rsplit(' ',1)[-1]
                tail=token if 0<len(token)<=12 else line[-1]
                line=line[:-len(tail)]
            lines.append(line);line=tail
        line+=char
    if line:lines.append(line)
    return lines

ROOT=STAGE/'data/source-v4'

def layout(model):
    width,height=A4; margin=20*72/25.4; y=height-margin;page=1;lines=[]
    for b in model['blocks']:
        level=b.get('level',0)
        size={1:21,2:16,3:13,4:12}.get(level,11)
        if b['type']=='frontmatter' and b['text'].startswith('문서 식별자:'):size=9
        if b['type']=='toc_heading':size=14
        leading=size*1.6
        texts=handbook_wrapped(b['text'],size,width-2*margin)
        # A chapter/section must stay with the chain of headings and two body lines.
        keep={1:60,2:104,3:76,4:42}.get(level,0)
        if (level or b['type']=='toc_heading') and y-leading*len(texts)-keep < margin:page+=1;y=height-margin
        for text in texts:
            if y-leading<margin:page+=1;y=height-margin
            lines.append(dict(text=text,x=margin,y=y,size=size,page=page,block_id=b.get('id'),type=b['type'],level=level))
            y-=leading
        y-=9 if level else 7
    return lines,page

def build(root,font,output):
    lock=read_json(STAGE/'authoring-lock.json')
    require(reportlab.Version==lock['reportlab_version'] and file_hash(font)==lock['font_sha256'],'dependency_mismatch','locked authoring environment required')
    require(embedding_flags(font)==lock['font_os2_fsType'],'font_permission','font embedding flags changed')
    source=root/'authoring/hr-handbook.md';model=parse(source.read_text())
    check_structure(model,read_json(root/'corpus-spec.json'))
    pdfmetrics.registerFont(TTFont('HRKorean',str(font)))
    lines,pages=layout(model)
    require(all(pdfmetrics.stringWidth(l['text'],'HRKorean',l['size'])<=A4[0]-40*72/25.4+.001 for l in lines),'layout','text exceeds body width')
    require(2<=pages<=48,'page_count','PDF page limit')
    with atomic_directory(output) as dest:
        (dest/'pdf').mkdir();path=dest/'pdf/hr-handbook.pdf'
        pdf=canvas.Canvas(str(path),pagesize=A4,invariant=1,pageCompression=1)
        pdf.setTitle('가상 HR 운영 규정집 | source-v4');pdf.setAuthor('Codex - fictional learning fixture')
        width,height=A4; margin=20*72/25.4
        for page in range(1,pages+1):
            for l in (l for l in lines if l['page']==page):
                pdf.setFont('HRKorean',l['size']);pdf.setFillColorRGB(*((.08,.25,.22) if l['level'] else (.13,.17,.16)))
                pdf.drawString(l['x'],l['y'],l['text'])
            pdf.setStrokeColorRGB(.8,.83,.82);pdf.line(margin,46,width-margin,46)
            pdf.setFillColorRGB(.35,.42,.40);pdf.setFont('Helvetica',8)
            pdf.drawString(margin,32,'HR-V4-HANDBOOK / v4');pdf.drawRightString(width-margin,32,str(page))
            pdf.showPage()
        pdf.save()
        write_json(dest/'pdf-authoring.json',dict(**lock,document_id=DID,effective_date=None,pages=pages,
          source_sha256=file_hash(source),pdf_sha256=file_hash(path),layout=dict(paper='A4',body_font_pt=11,margin_mm=20,columns=1,manual_page_breaks=0),
          font_note='Local macOS font; no OS/2 rights table; no standalone font redistribution. Matching licensed font required for byte-identical authoring.',lines=lines))
    return dict(pages=pages,pdf_sha256=file_hash(output/'pdf/hr-handbook.pdf'))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,default=ROOT);p.add_argument('--font',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    try:print(build(a.source_root,a.font,a.output_dir))
    except (ValueError,OSError,KeyError,TypeError) as e:return cli_error(e)
    return 0
if __name__=='__main__':raise SystemExit(main())
