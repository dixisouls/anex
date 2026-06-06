"""Pytest defaults: offline embeddings and no Weave for unit tests."""

import os

os.environ.setdefault("EMBEDDINGS_FAKE", "1")
os.environ.setdefault("WEAVE_DISABLED", "1")
