"""Import definitions only, network/weight/key access denied by audit hooks."""
import sys,json,os
attempts=[]
def forbidden_path(p):
 lower=os.fsdecode(p).lower();parts=lower.replace('\\','/').split('/')
 return lower.endswith(('.safetensors','.bin','.pt','.pth')) or any(x in parts for x in ('.ssh','.aws')) or parts[-1] in ('token','token.json','credentials','credentials.json','.env')
def audit(event,args):
 if event in ('socket.connect','socket.connect_ex','socket.getaddrinfo'):
  attempts.append(event);raise RuntimeError('network forbidden')
 if event=='open' and isinstance(args[0],(str,bytes)) and forbidden_path(args[0]):
  attempts.append('blocked_file');raise RuntimeError('weight/key read forbidden')
if __name__=='__main__':
 sys.addaudithook(audit)
 import torch
 from sentence_transformers import SentenceTransformer
 assert not attempts,attempts
 print(json.dumps({'status':'PASS','torch_version':torch.__version__,'SentenceTransformer_definition_imported':True,'model_instances':0,'weight_reads':0,'network_calls':0,'key_reads':0,'blocked_attempts':attempts,'isolated':sys.flags.isolated}))
