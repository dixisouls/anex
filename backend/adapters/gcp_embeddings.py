"""
GCP embeddings via the Google Gen AI SDK (Gemini Enterprise Agent Platform).
"""

import numpy as np
from google import genai
from google.genai import types

from backend.config import GCP_EMBED_MODEL, GCP_LOCATION, GCP_PROJECT, VECTOR_DIM


class GcpEmbeddings:
    def __init__(self) -> None:
        self._client = genai.Client(
            vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION
        )

    def embed(self, text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
        resp = self._client.models.embed_content(
            model=GCP_EMBED_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=VECTOR_DIM,
                task_type=task_type,
            ),
        )
        values = resp.embeddings[0].values
        arr = np.asarray(values, dtype=np.float32)
        if arr.shape[0] != VECTOR_DIM:
            raise ValueError(
                f"{GCP_EMBED_MODEL} returned dim {arr.shape[0]}, "
                f"expected VECTOR_DIM={VECTOR_DIM}"
            )
        norm = float(np.linalg.norm(arr))
        return arr / norm if norm > 0.0 else arr

    def embed_bytes(self, text: str, *, task_type: str = "RETRIEVAL_DOCUMENT") -> bytes:
        return self.embed(text, task_type=task_type).tobytes()
