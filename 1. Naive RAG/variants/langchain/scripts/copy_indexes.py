#!/usr/bin/env python3
"""Copy quiescent local Qdrant indexes without re-embedding or changing source."""
import argparse,hashlib,json,shutil
from pathlib import Path
import portalocker
from qdrant_client import QdrantClient
from runtime_common import STAGE

def logical(path):
 client=QdrantClient(path=str(path/'store'))
 try:
  points,offset=client.scroll('hr_chunks',limit=10000,with_vectors=True,with_payload=True)
  if offset is not None:raise ValueError('index exceeds supported snapshot size')
  value={'points':sorted([p.model_dump(mode='json') for p in points],key=lambda x:x['id']),
         'settings':client.get_collection('hr_chunks').config.model_dump(mode='json')}
 finally:client.close()
 return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def snapshot(source,destination):
 source=Path(source).resolve();destination=Path(destination).resolve()
 if destination.exists() or not (source/'store/.lock').is_file():raise ValueError('source must exist and destination must be new')
 destination.parent.mkdir(parents=True,exist_ok=True)
 # Uses the same exclusive lock as Qdrant. Never deletes another process lock.
 with (source/'store/.lock').open('r+b') as lock:
  portalocker.lock(lock,portalocker.LOCK_EX|portalocker.LOCK_NB)
  shutil.copytree(source,destination,ignore=shutil.ignore_patterns('.lock'))
  portalocker.unlock(lock)
 a,b=logical(source),logical(destination)
 if a!=b:raise ValueError('snapshot logical hash mismatch; preserve for diagnosis')
 return {'source':str(source),'destination':str(destination),'logical_sha256':a,'status':'PASS'}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-runtime',type=Path,required=True);args=p.parse_args()
 print(json.dumps([snapshot(args.source_runtime/name,STAGE/'.runtime'/name) for name in ['index-v1','index-source-v2-fixed-400-80']],indent=2))
