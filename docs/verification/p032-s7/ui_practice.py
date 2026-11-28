"""Serve the installed practice's three stored chunk sets with execution disabled."""
from pathlib import Path
import json
from rag_package.ui_server import create_server

e=Path(__file__).resolve().parent
ws=Path(json.loads((e/'installation.json').read_text())['base'])/'practice'
methods=('structure','handbook')
server=create_server(ws,[ws/'llm-local.json'],sources=ws/'handbook-sources.json',port=0,chunk_configs=[ws/f'chunk-{m}.json' for m in methods])
print(server.origin,flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
