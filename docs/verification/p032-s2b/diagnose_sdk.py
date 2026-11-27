"""Post-stop import-only diagnostic. Never construct a model or read weights."""
import sys,json,traceback,socket
from pathlib import Path
events=[]
class NoSocket(socket.socket):
    def __init__(self,*a,**k):raise RuntimeError('diagnostic network denied')
socket.socket=NoSocket
def audit(name,args):
    if name=='open' and args and isinstance(args[0],str) and args[0].endswith(('.safetensors','.bin','.pt','.pth')):
        raise RuntimeError('diagnostic weights denied')
sys.addaudithook(audit)
result={'scope':'SDK import only, no model/embedding/worker retry','model_calls':0,'weight_reads':0,'network_calls':0}
try:
    import torch
    events.append('torch imported')
    def deny(*a,**k):raise RuntimeError('diagnostic model loading denied')
    torch.load=deny
    from sentence_transformers import SentenceTransformer
    events.append('SentenceTransformer class imported, constructor not called')
    result.update(status='imports_pass',torch=str(torch.__version__))
except BaseException as e:
    result.update(status='import_failed',exception_type=type(e).__name__,exception=str(e),traceback=traceback.format_exc())
result['events']=events
print(json.dumps(result,ensure_ascii=False,indent=2))
