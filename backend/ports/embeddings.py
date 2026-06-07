"""Embeddings port: text to L2-normalized vectors for KNN search."""

from typing import Protocol

import numpy as np


class Embeddings(Protocol):
    def embed(self, text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> np.ndarray: ...

    def embed_bytes(self, text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> bytes: ...
