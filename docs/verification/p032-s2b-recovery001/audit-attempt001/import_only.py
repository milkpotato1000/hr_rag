"""Import definitions only, network/weight/key access denied by audit hooks."""
import sys,json,os
attempts=[]
def audit(event,args):
 if event in ('socket.connect','socket.connect_ex','socket.getaddrinfo'):
  attempts.append(event);raise RuntimeError('network forbidden')
 if event=='open' and isinstance(args[0],(str,bytes)):
  p=os.fsdecode(args[0]);lower=p.lower()
  if lower.endswith(('.safetensors','.bin','.pt','.pth')) or any(x in lower for x in ('/.ssh/','/.aws/','/token','/credentials')):
   # Python package source named tokenization is not a credential.
   if '/site-packages/' in lower and lower.endswith(('.py','.pyc','.so')):return
   attempts.append('blocked_file');raise RuntimeError('weight/key read forbidden')
sys.addaudithook(audit)
import torch
from sentence_transformers import SentenceTransformer
assert not attempts,attempts
print(json.dumps({'status':'PASS','torch_version':torch.__version__,'SentenceTransformer_definition_imported':True,'model_instances':0,'weight_reads':0,'network_calls':0,'key_reads':0,'blocked_attempts':attempts,'isolated':sys.flags.isolated}))
