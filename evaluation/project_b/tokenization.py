"""Offline Qwen2 byte BPE using the installed GGUF vocabulary and merges.

Pretokenizer alternatives follow Qwen's published Qwen2 tokenizer regex:
https://github.com/huggingface/transformers/blob/main/src/transformers/models/qwen2/tokenization_qwen2.py
No vocabulary downloads, model loads, or character-as-token estimates.
Only the pinned single-user, no-tools, think=false template is supported.
"""
import re
import unicodedata
from functools import lru_cache


def letter(c):
    return bool(c) and unicodedata.category(c).startswith('L')


def number(c):
    return bool(c) and unicodedata.category(c).startswith('N')


def pieces(text):
    i = 0
    while i < len(text):
        start = i
        m = re.match(r"(?i:'s|'t|'re|'ve|'m|'ll|'d)", text[i:])
        if m:
            i += len(m[0])
        elif letter(text[i]) or (text[i] not in '\r\n' and not number(text[i])
                                and i+1 < len(text) and letter(text[i+1])):
            i += 1
            while i < len(text) and letter(text[i]): i += 1
        elif number(text[i]):
            i += 1
        else:
            j = i + (text[i] == ' ')
            while j < len(text) and not text[j].isspace() and not letter(text[j]) and not number(text[j]): j += 1
            if j > i + (text[i] == ' '):
                while j < len(text) and text[j] in '\r\n': j += 1
                i = j
            else:
                j = i
                while j < len(text) and text[j].isspace(): j += 1
                last_newline = max(text.rfind('\n', i, j), text.rfind('\r', i, j))
                if last_newline >= i:
                    i = last_newline + 1
                elif j == len(text) or j-i <= 1:
                    i = max(j, i+1)
                else:
                    i = j-1
        yield text[start:i]


class QwenTokenizer:
    def __init__(self, model_info):
        if (model_info['tokenizer.ggml.model'], model_info['tokenizer.ggml.pre'],
                model_info['tokenizer.ggml.add_bos_token']) != ('gpt2', 'qwen2', False):
            raise ValueError('unsupported tokenizer')
        tokens = model_info['tokenizer.ggml.tokens']
        self.vocab = {t:i for i,t in enumerate(tokens)}
        self.ranks = {tuple(m.split(' ')):i for i,m in enumerate(model_info['tokenizer.ggml.merges'])}
        if not self.ranks or len(tokens) != len(self.vocab): raise ValueError('invalid vocabulary')
        bs = list(range(33,127)) + list(range(161,173)) + list(range(174,256))
        cs = bs.copy(); missing = [b for b in range(256) if b not in bs]
        self.alphabet = dict(zip(bs+missing, [chr(c) for c in cs+list(range(256,256+len(missing)))]))
        if not all(c in self.vocab for c in self.alphabet.values()): raise ValueError('missing byte token')
        types = model_info['tokenizer.ggml.token_type']
        self.specials = {t:i for i,t in enumerate(tokens) if types[i] in (3,4)}
        self.special_pattern = re.compile('|'.join(re.escape(t) for t in sorted(self.specials, key=len, reverse=True)))

    @lru_cache(maxsize=8192)
    def bpe(self, word):
        parts = [self.alphabet[b] for b in word.encode('utf-8')]
        while len(parts) > 1:
            candidates = [(self.ranks.get((a,b), float('inf')), i) for i,(a,b) in enumerate(zip(parts,parts[1:]))]
            rank, i = min(candidates)
            if rank == float('inf'): break
            parts[i:i+2] = [parts[i]+parts[i+1]]
        return tuple(self.vocab[p] for p in parts)

    def encode(self, text):
        ids = []; start = 0
        for m in self.special_pattern.finditer(text):
            for p in pieces(text[start:m.start()]): ids.extend(self.bpe(p))
            ids.append(self.specials[m[0]]); start = m.end()
        for p in pieces(text[start:]): ids.extend(self.bpe(p))
        return ids

    def chat(self, messages):
        if len(messages) != 1 or messages[0]['role'] != 'user':
            raise ValueError('only verified single-user template supported')
        return '<|im_start|>user\n'+messages[0]['content']+' /no_think<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'

    def count(self, messages):
        return len(self.encode(self.chat(messages)))
