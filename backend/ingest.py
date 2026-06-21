"""
ingest.py — PDF ingestion pipeline.

Steps:
  1. Parse PDF pages with pdfplumber (handles text + tables).
  2. Chunk text into overlapping windows (~500 tokens each).
  3. Embed chunks with the OpenAI embeddings API.
  4. Store chunks + embeddings + metadata in ChromaDB.

Usage (standalone):
  python ingest.py --pdf data/pdfs/AAPL_Q4_2025.pdf --company AAPL
"""

import argparse
import hashlib
from pathlib import Path
from typing import Generator

import chromadb
import pdfplumber
from chromadb.config import Settings
from backend.embeddings import EMBED_MODEL, collection_name, embed_texts

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = collection_name()
CHUNK_SIZE = 500      # approximate tokens (1 token ≈ 4 chars, so ~2000 chars)
CHUNK_OVERLAP = 80    # token overlap between consecutive chunks

_collection = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """
    Extract text page-by-page using pdfplumber.
    Tables are serialised as plain text rows (tab-separated) so the LLM
    can still reason over them without special handling.

    Returns a list of {page_num, text} dicts.
    """
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            parts = []

            # --- Body text ---
            body = page.extract_text(x_tolerance=2, y_tolerance=2)
            if body:
                parts.append(body)

            # --- Tables ---
            for table in page.extract_tables():
                rows = []
                for row in table:
                    cleaned = [str(c).strip() if c else "" for c in row]
                    rows.append("\t".join(cleaned))
                parts.append("\n".join(rows))

            combined = "\n".join(parts).strip()
            if combined:
                pages.append({"page_num": i, "text": combined})

    return pages


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> Generator[str, None, None]:
    """
    Simple word-level sliding-window chunker.
    chunk_size and overlap are in *words* (close enough to tokens for
    sentence-transformer models).
    """
    words = text.split()
    if not words:
        return

    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        yield " ".join(words[start:end])
        if end == len(words):
            break
        start += chunk_size - overlap


def _chunk_id(company: str, filename: str, page: int, chunk_idx: int) -> str:
    """Deterministic, reproducible chunk ID so re-ingestion is idempotent."""
    raw = f"{company}::{filename}::p{page}::c{chunk_idx}"
    return hashlib.md5(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_pdf(pdf_path: str, company: str) -> int:
    """
    Ingest a single PDF into ChromaDB.
    Returns the number of chunks stored.
    """
    pdf_path = str(pdf_path)
    filename = Path(pdf_path).name
    print(f"[ingest] Processing: {filename} → company={company}")

    pages = _extract_text_from_pdf(pdf_path)
    print(f"[ingest] Extracted {len(pages)} pages")

    collection = _get_collection()

    all_ids, all_docs, all_metas = [], [], []

    for page_data in pages:
        page_num = page_data["page_num"]
        for chunk_idx, chunk in enumerate(_chunk_text(page_data["text"])):
            chunk = chunk.strip()
            if len(chunk) < 50:   # skip tiny fragments
                continue

            chunk_id = _chunk_id(company, filename, page_num, chunk_idx)

            all_ids.append(chunk_id)
            all_docs.append(chunk)
            all_metas.append({
                "company": company,
                "filename": filename,
                "page_num": page_num,
                "chunk_idx": chunk_idx,
            })

    if not all_ids:
        print("[ingest] Warning: no chunks produced — check PDF text layer")
        return 0

    # Upsert in batches of 100
    batch_size = 100
    for i in range(0, len(all_ids), batch_size):
        batch_docs = all_docs[i:i+batch_size]
        print(
            f"[ingest] Embedding batch {i // batch_size + 1} "
            f"with {EMBED_MODEL} ({len(batch_docs)} chunks)"
        )
        collection.upsert(
            ids=all_ids[i:i+batch_size],
            documents=batch_docs,
            embeddings=embed_texts(batch_docs),
            metadatas=all_metas[i:i+batch_size],
        )

    print(f"[ingest] Stored {len(all_ids)} chunks for {filename}")
    return len(all_ids)


def ingest_directory(pdf_dir: str, company_map: dict[str, str]) -> dict[str, int]:
    """
    Ingest multiple PDFs.
    company_map: {filename_stem: company_tag}
    e.g. {"AAPL_Q4_2025": "AAPL", "Alphabet_Q4_2025": "GOOGLE"}
    """
    results = {}
    for stem, company in company_map.items():
        path = Path(pdf_dir) / f"{stem}.pdf"
        if path.exists():
            results[stem] = ingest_pdf(str(path), company)
        else:
            print(f"[ingest] File not found, skipping: {path}")
    return results


def list_ingested(allowed_companies: list[str] | None = None) -> list[dict]:
    """Return an optionally access-filtered summary of ingested documents."""
    collection = _get_collection()
    result = collection.get(include=["metadatas"])
    metadatas = result["metadatas"]
    if allowed_companies is not None:
        allowed = set(allowed_companies)
        metadatas = [meta for meta in metadatas if meta["company"] in allowed]

    companies: dict[str, set] = {}
    for meta in metadatas:
        c = meta["company"]
        companies.setdefault(c, set()).add(meta["filename"])
    return [{"company": c, "files": list(files), "chunks": sum(1 for m in metadatas if m["company"] == c)}
            for c, files in companies.items()]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a PDF into ChromaDB")
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--company", required=True, help="Company tag (e.g. AAPL)")
    args = parser.parse_args()

    count = ingest_pdf(args.pdf, args.company.upper())
    print(f"Done. {count} chunks ingested.")
