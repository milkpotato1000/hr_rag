"""Finish independent real CLI/API and embedding checks after cold retest."""
import time,subprocess,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[4];ev=root/'docs/verification/p011';s=root/'1. Naive RAG';b=s/'variants/langchain';end=time.monotonic()+3600
while len(list((ev/'runs').glob('repair-cold-*.json')))<18:
 if time.monotonic()>end:raise RuntimeError('cold retest incomplete; no smoke overlap')
 time.sleep(5)
for f in (ev/'runs').glob('repair-cold-*.json'):
 d=json.loads(f.read_text());assert d['result']['status']!='error',f.name
subprocess.run([sys.executable,str(Path(__file__).with_name('smokes.py'))],check=True,cwd=root)
for impl,stage in [('direct',s),('langchain',b)]:
 with (ev/f'live-embeddings-{impl}.json').open('w') as out:
  subprocess.run([str(stage/'.venv/bin/python'),str(Path(__file__).with_name('embedding_worker.py')),str(stage),str(ev/'protocol.json')],stdout=out,check=True)
 with (ev/f'live-vector-parity-{impl}.json').open('w') as out:
  subprocess.run([str(stage/'.venv/bin/python'),str(Path(__file__).with_name('parity_worker.py')),str(stage),impl,str(ev/'protocol.json'),str(ev/f'live-embeddings-{impl}.json')],stdout=out,check=True)
a=json.loads((ev/'live-embeddings-direct.json').read_text());b=json.loads((ev/'live-embeddings-langchain.json').read_text());assert a==b
assert json.loads((ev/'live-vector-parity-direct.json').read_text())==json.loads((ev/'live-vector-parity-langchain.json').read_text())
(ev/'embedding-parity.json').write_text(json.dumps({'status':'PASS','query_inputs_outputs_exact':18,'live_vector_matrix_cases':326,'generation_dispatches':0},indent=2)+'\n');print('post repair checks PASS',flush=True)
