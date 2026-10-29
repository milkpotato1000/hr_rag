"""Persistent local cosine index. Fixtures use this boundary with known vectors."""
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from qdrant_client import QdrantClient, models
from model_runtime import validate_vector
from document_common import write_json

COLLECTION = 'hr_chunks'
FIELDS = ('chunk_id', 'document_id', 'version', 'title', 'text', 'source', 'synthetic')
TEXT_VERSION = 'canonical-slice-only-v1'


def point_id(chunk_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'synthetic-hr-rag:' + chunk_id))


def manifest_for(chunks, corpus_hash, lock):
    version = importlib.metadata.version('qdrant-client')
    if version != lock['qdrant_client_version']:
        raise ValueError('Qdrant client differs from runtime lock')
    return {'schema_version': 1, 'corpus_sha256': corpus_hash, 'model_name': lock['model']['name'],
            'model_digest': lock['model']['digest'], 'dimension': lock['model']['dimension'],
            'runtime_version': lock['ollama']['version'], 'text_version': TEXT_VERSION, 'truncate': False,
            'distance': 'Cosine', 'qdrant_client_version': version, 'point_count': len(chunks),
            'id_version': 'uuid5-url-hr-v1'}


def check_new_path(path):
    path = Path(path)
    if os.path.lexists(path) or not path.parent.is_dir():
        raise ValueError('destination must be a new path with an existing parent: ' + str(path))
    return path


def publish_index(staging, destination):
    destination.mkdir()
    try:
        for child in staging.iterdir():
            if child.is_dir():
                shutil.copytree(child, destination / child.name)
            else:
                with child.open('rb') as source, (destination / child.name).open('xb') as output:
                    shutil.copyfileobj(source, output)
    except BaseException:
        shutil.rmtree(destination)
        raise


def create_index(chunks, corpus_hash, vectors, lock, destination, before_publish=None):
    destination = check_new_path(destination)
    manifest = manifest_for(chunks, corpus_hash, lock)
    ids = sorted(chunks)
    if len(vectors) != len(ids):
        raise ValueError('document embedding count mismatch')
    for vector in vectors:
        validate_vector(vector, manifest['dimension'])
    with tempfile.TemporaryDirectory(prefix='.dense-index-', dir=destination.parent) as scratch:
        staging = Path(scratch)
        client = QdrantClient(path=str(staging / 'store'))
        try:
            client.create_collection(COLLECTION, vectors_config=models.VectorParams(size=manifest['dimension'], distance=models.Distance.COSINE))
            client.upsert(COLLECTION, points=[models.PointStruct(id=point_id(cid), vector=vector,
                          payload={key: chunks[cid][key] for key in FIELDS}) for cid, vector in zip(ids, vectors)], wait=True)
            if client.count(COLLECTION, exact=True).count != len(ids):
                raise ValueError('index point count mismatch')
        finally:
            client.close()
        write_json(staging / 'index-manifest.json', manifest)
        with DenseIndex(staging, chunks, corpus_hash, lock):
            pass
        if before_publish:
            before_publish()
        publish_index(staging, destination)
    return manifest


class DenseIndex:
    def __init__(self, path, chunks, corpus_hash, lock):
        self.path, self.chunks = Path(path), chunks
        self.manifest = manifest_for(chunks, corpus_hash, lock)
        if not (self.path / 'index-manifest.json').is_file() or not (self.path / 'store/meta.json').is_file():
            raise ValueError('complete persistent index is missing; build a new index')
        if json.loads((self.path / 'index-manifest.json').read_text()) != self.manifest:
            raise ValueError('stale index manifest; build a new index path')
        self.client = QdrantClient(path=str(self.path / 'store'))
        try:
            config = self.client.get_collection(COLLECTION).config.params.vectors
            if config.size != self.manifest['dimension'] or config.distance != models.Distance.COSINE:
                raise ValueError('index vector configuration mismatch')
            if self.client.count(COLLECTION, exact=True).count != len(chunks):
                raise ValueError('index count differs from corpus')
            records, offset = self.client.scroll(COLLECTION, limit=len(chunks) + 1, with_payload=True, with_vectors=True)
            if offset is not None:
                raise ValueError('unexpected extra index points')
            self.validate_points(records, vectors=True)
        except BaseException:
            self.client.close()
            raise

    def validate_points(self, points, vectors=False):
        if len(points) != len(self.chunks):
            raise ValueError('expected all corpus candidates')
        seen = set()
        for point in points:
            payload = point.payload
            cid = payload.get('chunk_id') if isinstance(payload, dict) else None
            if not isinstance(cid, str) or cid not in self.chunks or cid in seen or str(point.id) != point_id(cid):
                raise ValueError('unknown payload, duplicate point, or ID mismatch')
            if payload != {key: self.chunks[cid][key] for key in FIELDS}:
                raise ValueError('payload differs from source corpus')
            if vectors:
                validate_vector(point.vector, self.manifest['dimension'])
            seen.add(cid)

    def search(self, vector, top_k):
        if type(top_k) is not int or top_k <= 0:
            raise ValueError('top-k must be a positive integer')
        validate_vector(vector, self.manifest['dimension'])
        hits = self.client.query_points(COLLECTION, query=vector, limit=len(self.chunks),
                                        with_payload=True).points
        self.validate_points(hits)
        rows = []
        for point in hits:
            if type(point.score) not in (int, float) or not math.isfinite(point.score):
                raise ValueError('invalid cosine score')
            rows.append({'chunk_id': point.payload['chunk_id'], 'score': point.score})
        return sorted(rows, key=lambda row: (-row['score'], row['chunk_id']))[:top_k]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()
