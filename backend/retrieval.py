"""
retrieval.py — Semantic retrieval with server-side access control.

The `allowed_companies` filter is enforced inside ChromaDB's `where` clause,
meaning a user physically cannot receive chunks from companies they are not
authorised to view — regardless of what they type in the query box.
"""

import chromadb
from chromadb.config import Settings
from pathlib import Path
from backend.embeddings import collection_name, embed_texts

CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = collection_name()
TOP_K = 5          # number of chunks to retrieve per query

_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def retrieve(
    query: str,
    allowed_companies: list[str],
    top_k: int = TOP_K,
) -> list[dict]:
    """
    Embed `query`, then search ChromaDB restricted to `allowed_companies`.

    Returns a list of result dicts:
        {
          "text":     str,   # chunk content
          "company":  str,
          "filename": str,
          "page_num": int,
          "score":    float, # cosine similarity (0–1, higher = better)
        }
    """
    if not allowed_companies:
        return []

    query_embedding = embed_texts([query])[0]

    # Build ChromaDB where-filter
    if len(allowed_companies) == 1:
        where_filter = {"company": {"$eq": allowed_companies[0]}}
    else:
        where_filter = {"company": {"$in": allowed_companies}}

    collection = _get_collection()

    # Guard: if the collection is empty, return early
    if collection.count() == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text":     doc,
            "company":  meta["company"],
            "filename": meta["filename"],
            "page_num": meta["page_num"],
            "score":    round(1 - dist, 4),   # cosine distance → similarity
        })

    # Sort by descending similarity
    chunks.sort(key=lambda x: x["score"], reverse=True)
    return chunks
