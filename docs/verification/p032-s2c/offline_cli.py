import sys,os,socket,subprocess
from unittest.mock import patch
import rag_package
assert "/env/" in rag_package.__file__
def deny(*a,**k): raise AssertionError("S2c forbids network/worker/key access")
original=os._Environ.__getitem__
def no_key(self,key):
    if any(word in str(key).upper() for word in ("API_KEY","TOKEN","CREDENTIAL","SECRET")):deny()
    return original(self,key)
llm=sys.argv[1:2]==["--llm"]
if llm:
    from rag_package.llm.__main__ import main
    argv=sys.argv[2:]
else:
    from rag_package.__main__ import main
    argv=sys.argv[1:]
with patch.object(socket.socket,"connect",deny),patch.object(socket,"create_connection",deny),patch.object(socket,"getaddrinfo",deny),patch.object(subprocess,"Popen",deny),patch.object(os._Environ,"__getitem__",no_key):
    raise SystemExit(main(argv))
