"""Explicit implementation dispatch; no fallback or parent-stage imports."""
import uuid
from importlib.metadata import version
from rag import ask as direct_ask


DEFAULT_IMPLEMENTATION = 'langchain'


def ask(*, implementation=DEFAULT_IMPLEMENTATION, **kwargs):
    if implementation not in ('direct', 'langchain'):
        return {'status': 'error', 'answer': 'implementation must be direct or langchain',
                'citations': [], 'reason': 'input',
                'trace': {'error': {'kind': 'input', 'message': 'invalid implementation'}}}
    if implementation == 'langchain':
        from rag_langchain import ask as pipeline
    else:
        pipeline = direct_ask
    result = pipeline(**kwargs)
    result['trace']['comparison'] = {'implementation': implementation,
        'run_id': str(uuid.uuid4()), 'langchain_core_version': version('langchain-core')}
    return result
