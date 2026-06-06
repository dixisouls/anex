"""Select Queue, EventBus, and Embeddings adapters by RUNTIME_ENV."""

from functools import lru_cache

from backend.config import RUNTIME_ENV
from backend.ports.embeddings import Embeddings
from backend.ports.event_bus import EventBus
from backend.ports.queue import Queue


@lru_cache
def get_queue() -> Queue:
    if RUNTIME_ENV == "gcp":
        raise NotImplementedError("GCP Cloud Tasks queue adapter ships in Branch 7")
    from backend.adapters.local_queue import LocalQueue

    return LocalQueue()


@lru_cache
def get_event_bus() -> EventBus:
    if RUNTIME_ENV == "gcp":
        raise NotImplementedError("GCP Pub/Sub event bus adapter ships in Branch 7")
    from backend.adapters.local_event_bus import LocalEventBus

    return LocalEventBus()


@lru_cache
def get_embeddings() -> Embeddings:
    from backend.infra.embeddings import get_embeddings as _get

    return _get()
