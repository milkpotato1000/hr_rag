"""Initialize a fresh practice directory with the S10 installed CLI."""
from pathlib import Path
import hashlib, json, shutil, subprocess, tempfile
E = Path(__file__).resolve().parent
def read(path):
    return json.loads(path.read_text())
prior = read(E.parent / 'p032-s10/verified.json')
base = Path(prior['commands'][0]['cwd'])
wheel, = (base/'dist').glob('*.whl')
assert hashlib.sha256(wheel.read_bytes()).hexdigest() == prior['wheel_sha256']
ws = Path(tempfile.mkdtemp(prefix='p032-s11-')).resolve() / 'practice'
cli = base/'env/bin/rag-lab'
subprocess.run([cli, 'init','--out',ws],check=True)
shutil.copyfile(E.parent/'p032-s8/profile.json',ws/'handbook-model.json')
q = '생일 특별휴가를 신청하면 누구의 승인을 받아야 하나요?'
for args in (['snapshot','--sources','handbook-sources.json','--out','snapshot'],
             ['build','--snapshot','snapshot','--config','fixed.json','--out','build'],
             ['ask','--run','build','--config','fixed.json','--question',q,'--out','preview']):
    subprocess.run([cli,*args],cwd=ws,check=True,stdout=subprocess.DEVNULL)
quote = '생일 특별휴가는 사용 3영업일 전까지 휴가 시스템에서 신청하고 팀장의 승인을 받아야 한다.'
assert any(quote in c['text'] and 'BD-03' in c['text'] for c in read(ws/'preview/result.json')['contexts'])
(E/'setup.json').write_text(json.dumps(dict(practice=str(ws),python=str(base/'env/bin/python'),question=q,quote=quote,wheel_sha256=prior['wheel_sha256']),ensure_ascii=False,indent=2)+'\n')
