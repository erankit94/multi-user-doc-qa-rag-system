"""OpenAI embedding client shared by ingestion and retrieval."""

import os
import re
from typing import Sequence

from openai import OpenAI

EMBED_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
EMBED_DIMENSIONS = int(os.environ.get("OPENAI_EMBEDDING_DIMENSIONS", "1536"))

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()  # Reads OPENAI_API_KEY from the environment.
    return _client


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Create embeddings for one or more non-empty text strings."""
    cleaned = [text.replace("\n", " ").strip() for text in texts]
    if not cleaned or any(not text for text in cleaned):
        raise ValueError("Embedding inputs must contain non-empty text")

    response = get_client().embeddings.create(
        model=EMBED_MODEL,
        input=cleaned,
        dimensions=EMBED_DIMENSIONS,
        encoding_format="float",
    )
    return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]


def collection_name() -> str:
    """Use a model-specific collection to avoid mixing incompatible vectors."""
    model_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", EMBED_MODEL).strip("-_")
    return f"documents-{model_slug}-{EMBED_DIMENSIONS}"
