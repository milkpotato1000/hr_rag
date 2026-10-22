#!/usr/bin/env python3
"""One-variable live HTTP example for the learning guide; not a holdout benchmark."""
import json
from pathlib import Path
from urllib.request import Request,urlopen

OUTPUT=Path(__file__).with_name('04-k-experiment')
QUESTION='생일 휴가의 자격과 신청 기한, 사용 기간을 함께 알려 주세요.'


def main():
    OUTPUT.mkdir()
    for k in [1,3,5,10]:
        request={'question':QUESTION,'retriever':'dense','top_k':k,'max_context_chars':8000}
        req=Request('http://127.0.0.1:8000/api/ask',data=json.dumps(request).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=300) as response:result=json.load(response)
        (OUTPUT/f'k{k}.json').write_text(json.dumps({'request':request,'result':result},ensure_ascii=False,indent=2)+'\n')
        print(k,result['status'],result['reason'],flush=True)


if __name__=='__main__':main()
