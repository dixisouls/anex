"""
Embeddings.

Turns the capability_text or a subtask into a vector. Two backends, chosen by the 
EMBED_BACKEND env var:

- "local" a deterministic, offline feature-hashing embedding. Not semantic, but
          it gives a crude lexical similarity (shared words land in shared
          buckets), enough to develop and test the registry, the index, and the 
          broker's matching with zero cloud setup. Same text always gives the
          same vector, across processes, because it hashes with hashlib rather
          than Python's salted hash.

- "vertex" calls Vertex AI text embeddings. Requires GCP credentials and the 
           google-cloud-aiplatform package. Output dimension must equal
           VECTOR_DIM or it raises, so a model/dimension mismatch fails loudly.

Both return raw little-endian float32 bytes, the format Redis vector field 
expects, via embed_bytes(). embed_vector() returns the numpy array if you need it.
"""

import hashlib
from multiprocessing import Value
import re

import numpy as np

from backend.config import (
    EMBED_BACKEND,
    VECTOR_DIM,
    VERTEX_EMBED_MODEL,
    VERTEX_PROJECT,
    VERTEX_LOCATION,
)

_TOKEN_RE = re.compile(r"[^a-z0-9]+")

def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.split(text.lower()) if t]

def _char_ngrams(tokens: str, n: int = 3) -> list[str]:
    """Character n-grams of a token, with boundry markers so prefixes and
    suffixes are captured. '#write#' shares most trigrams with '#writes#', which
    is what gives local embedding its lexical robustness."""
    s = f"#{tokens}#"
    if len(s) < n:
        return [s]
    return [s[i:i+n] for i in range(len(s) - n + 1)]

def _features(text: str) -> list[str]:
    feats: list[str] = []
    for token in _tokens(text):
        feats.append(token) # the whole word, weighted alongside its n-grams
        feats.extend(_char_ngrams(token))
    return feats

def _hash_feature(feature: str) -> tuple[int, float]:
    digest = hashlib.md5(feature.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "little") % VECTOR_DIM
    sign = 1.0 if (digest[4] & 1) else -1.0
    return bucket, sign

def _local_embed(text: str) -> np.ndarray:
    vec = np.zeros(VECTOR_DIM, dtype=np.float32)
    for feature in _features(text):
        bucket, sign = _hash_feature(feature)
        vec[bucket] += sign
    norm = float(np.linalg.norm(vec))
    if norm > 0.0:
        vec /= norm
    return vec

def _vertex_embed(text: str) -> np.ndarray:
    # Import lazily so local development needs no gcp packages installed.
    import vertexai
    from vertexai.language_models import TextEmbeddingModel

    vertexai.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION)
    model = TextEmbeddingModel.from_pretrained(VERTEX_EMBED_MODEL)
    values = model.get_embeddings([text])[0].values
    arr = np.asarray(values, dtype=np.float32)
    if arr.shape[0] != VECTOR_DIM:
        raise ValueError(
            f"Vertex model {VERTEX_EMBED_MODEL} returned dim {arr.shape[0]}, "
            f"but VECTOR_DIM is {VECTOR_DIM}. Set VECTOR_DIM to match the model "
            f"and rebuild the index."
        )
    return arr

def embed_vector(text: str) -> np.ndarray:
    if EMBED_BACKEND == "vertex":
        return _vertex_embed(text)
    return _local_embed(text)

def embed_bytes(text: str) -> bytes:
    """The form stored on the agent hash and passed as a KNN query param."""
    return embed_vector(text).astype(np.float32).tobytes()