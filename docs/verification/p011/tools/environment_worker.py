import json,sys,platform,importlib.metadata,time,resource
from pathlib import Path
stage=Path(sys.argv[1]);impl=sys.argv[2];sys.path.insert(0,str(stage/'scripts'));start=time.perf_counter()
if impl=='langchain':import rag_langchain
else:import rag
import_ms=(time.perf_counter()-start)*1000
print(json.dumps({'python':platform.python_version(),'machine':platform.machine(),'system':platform.system(),'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'venv_regular_file_bytes':sum(p.stat().st_size for p in (stage/'.venv').rglob('*') if p.is_file() and not p.is_symlink()),'import_ms':import_ms,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
