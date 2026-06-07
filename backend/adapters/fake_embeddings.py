"""
Deterministic offline embeddings for tests and local dev without GCP credentials.

Set EMBEDDINGS_FAKE=1 to select this adapter via get_embeddings().
"""

import hashlib
import re

import numpy as np

from backend.config import VECTOR_DIM

_TOKEN_RE = re.compile(r"[^a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.split(text.lower()) if t]


def _char_ngrams(token: str, n: int = 3) -> list[str]:
    s = f"#{token}#"
    if len(s) < n:
        return [s]
    return [s[i : i + n] for i in range(len(s) - n + 1)]


def _features(text: str) -> list[str]:
    feats: list[str] = []
    for token in _tokens(text):
        feats.append(token)
        feats.extend(_char_ngrams(token))
    return feats


def _hash_feature(feature: str) -> tuple[int, float]:
    digest = hashlib.md5(feature.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "little") % VECTOR_DIM
    sign = 1.0 if (digest[4] & 1) else -1.0
    return bucket, sign


class FakeEmbeddings:
    def embed(self, text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
        vec = np.zeros(VECTOR_DIM, dtype=np.float32)
        for feature in _features(text):
            bucket, sign = _hash_feature(feature)
            vec[bucket] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0.0:
            vec /= norm
        return vec

    def embed_bytes(self, text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> bytes:
        return self.embed(text, task_type=task_type).tobytes()
