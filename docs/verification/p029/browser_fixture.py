"""Owned installed-wheel browser fixture. Not included in application distribution."""
from pathlib import Path
import hashlib,json,os,signal,socket,sys,time
from rag_package.workspace import init
from rag_package.ui_server import create_server
import rag_package
base=Path.cwd();assert 'site-packages' in rag_package.__file__ and str(base) in rag_package.__file__;assert 'PYTHONPATH' not in os.environ
ws=base/'browser-workspace';init(ws)
text='생일 특별휴가 😀\n입사 후 3개월이 지난 재직자는 매년 1일 신청할 수 있습니다. 수습 중인 직원은 제외됩니다. 사용 3영업일 전 신청하고 팀장 승인을 받습니다. 생일 달 근무일에 사용합니다.\n'+('장문 근거 😀: 예외 요청은 인사 담당자가 확인하며 승인 전 사용으로 처리하지 않습니다. 관련 신청 내역을 보관합니다. '*12)
(ws/'documents/birthday.md').write_text('# 가상 생일휴가\n'+text,encoding='utf-8')
c=json.loads((ws/'llm-api.json').read_text());p=c['profiles'][c['roles']['generation']];p['model']='fake-browser-model';p['identity'].update(requested_model='fake-browser-model',validation_status='user_configured_unverified');(ws/'llm-api.json').write_text(json.dumps(c),encoding='utf-8')
counts={'generation':0,'drive':0}
def model(method,url,headers,body,timeout):
    assert method=='POST';counts['generation']+=1;time.sleep(.4)
    data=json.loads(body['messages'][-1]['content']);cid=data['contexts'][0]['chunk_id'];content=json.dumps({'status':'answered','answer':'가상 검증 응답: 생일 특별휴가 자격과 절차는 아래 원문 인용을 확인하세요.','citations':[{'chunk_id':cid}]},ensure_ascii=False)
    return {'model':body['model'],'choices':[{'message':{'role':'assistant','content':content},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':30}}
raw=text.encode();meta={'id':'example_file_id','name':'가상 Drive 문서 😀.txt','mimeType':'text/plain','version':'1','modifiedTime':'2026-11-27T00:00:00Z','trashed':False,'capabilities':{'canDownload':True},'size':str(len(raw)),'sha256Checksum':hashlib.sha256(raw).hexdigest()}
def drive(url,headers,limit,deadline):
    counts['drive']+=1;return raw if 'alt=media' in url else json.dumps(meta,ensure_ascii=False).encode()
def forbidden(*a,**k):raise AssertionError('actual network forbidden')
socket.socket.connect=forbidden;socket.getaddrinfo=forbidden
s=create_server(ws,[ws/'llm-local.json',ws/'llm-api.json'],ws/'sources.json',[ws/'drive-token-env.json'],port=0,allow_model=True,allow_drive=True,transport=model,key_resolver=lambda _:'SYNTHETIC_BROWSER_TOKEN',drive_transport=drive,env_resolver=lambda _:'SYNTHETIC_DRIVE_TOKEN')
record={'url':s.origin,'pid':os.getpid(),'workspace':str(ws),'package_import':rag_package.__file__,'execution_kind':'test_fixture','actual_network_calls':0}
(base/'browser-server.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
try:s.serve_forever()
except KeyboardInterrupt:pass
finally:
    s.server_close();record.update(stopped=True,fake_calls=counts);(base/'browser-server.json').write_text(json.dumps(record,indent=2)+'\n')
