"""P002 BM25 with P007 text-only input; title is display metadata."""
from collections import Counter
import math,re,unicodedata
class evaluation:
    InputError=ValueError
TOKEN_PATTERN=r"[^\W_]+"
K1=1.2
B=.75

def tokenize(value):
    return re.findall(TOKEN_PATTERN, unicodedata.normalize("NFKC", value).casefold())

class BM25Index:
    """Index corpus text only. No query labels or relevance enter this class."""

    def __init__(self, chunks):
        if not chunks:
            raise evaluation.InputError("corpus must not be empty")
        self.counts = {}
        self.document_frequency = Counter()
        for chunk_id, chunk in sorted(chunks.items()):
            counts = Counter(tokenize(chunk["text"]))
            self.counts[chunk_id] = counts
            self.document_frequency.update(counts.keys())
        self.lengths = {chunk_id: sum(counts.values()) for chunk_id, counts in self.counts.items()}
        self.n = len(self.counts)
        self.avgdl = sum(self.lengths.values()) / self.n

    def search(self, question, top_k):
        if type(top_k) is not int or top_k <= 0:
            raise evaluation.InputError("top-k must be a positive integer")
        if not isinstance(question, str):
            raise evaluation.InputError("question must be a string")
        tokens = sorted(set(tokenize(question)))
        results = []
        if not tokens or self.avgdl == 0:
            return tokens, results
        for chunk_id, counts in self.counts.items():
            score = 0.0
            norm = K1 * (1 - B + B * self.lengths[chunk_id] / self.avgdl)
            for token in tokens:
                tf = counts.get(token, 0)
                if not tf:
                    continue
                df = self.document_frequency[token]
                idf = math.log(1 + (self.n - df + 0.5) / (df + 0.5))
                score += idf * tf * (K1 + 1) / (tf + norm)
            if not math.isfinite(score):
                raise evaluation.InputError("non-finite BM25 score")
            if score > 0:
                results.append({"chunk_id": chunk_id, "score": score})
        results.sort(key=lambda row: (-row["score"], row["chunk_id"]))
        return tokens, results[:top_k]
