"""
Embeddings entry point. GCP is the production path; set EMBEDDINGS_FAKE=1 for offline tests.
"""

import os
from functools import lru_cache

from backend.adapters.fake_embeddings import FakeEmbeddings


@lru_cache
def get_embeddings() -> FakeEmbeddings:
    if os.getenv("EMBEDDINGS_FAKE", "0") == "1":
        return FakeEmbeddings()
    from backend.adapters.gcp_embeddings import GcpEmbeddings

    return GcpEmbeddings()


def embed_bytes(text: str) -> bytes:
    return get_embeddings().embed_bytes(text)
