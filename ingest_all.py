#!/usr/bin/env python3
"""
ingest_all.py — One-shot script to ingest all earnings-call PDFs.

Edit PDF_MAP below to match your filenames and company tags, then run:
    python ingest_all.py

The company tags must match exactly what's in backend/auth.py USER_ACCESS.
"""

import sys
from pathlib import Path

# Make sure project root is on sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.ingest import ingest_pdf, list_ingested

# ---------------------------------------------------------------------------
# Edit this map: { pdf_filename_in_data/pdfs/ : company_tag }
# ---------------------------------------------------------------------------
PDF_MAP = {
    "Alphabet_Q4_2025.pdf": "GOOGLE",
    "AMD_Q4_2025.pdf": "AMD",
    "META_Q4_2025.pdf": "META",
    "Microsoft_Q4_2025.pdf": "MSFT",
    "Netflix_Q4_2025.pdf": "NFLX",
}

PDF_DIR = ROOT / "data" / "pdfs"

# # Auto-detect all PDFs in data/pdfs/
# # Filename convention: <COMPANY_TAG>_anything.pdf
# # e.g. AAPL_Q4_2025.pdf → company tag = "AAPL"
# PDF_MAP = {}
# for pdf_file in PDF_DIR.glob("*.pdf"):
#     company_tag = pdf_file.stem.split("_")[0].upper()  # "AAPL_Q4_2025" → "AAPL"
#     PDF_MAP[pdf_file.name] = company_tag

def main():
    print("=" * 60)
    print("  DocuSearch — PDF Ingestion Script")
    print("=" * 60)

    any_ingested = False
    for filename, company in PDF_MAP.items():
        pdf_path = PDF_DIR / filename
        if not pdf_path.exists():
            print(f"⚠  Not found, skipping: {pdf_path}")
            continue
        print(f"\n→ Ingesting {filename} as {company}…")
        count = ingest_pdf(str(pdf_path), company)
        print(f"  ✓  {count} chunks stored")
        any_ingested = True 

    if not any_ingested:
        print(
            "\n⚠  No PDFs were found in data/pdfs/. "
            "Copy your earnings-call PDFs there and re-run."
        )
        return

    print("\n" + "=" * 60)
    print("  Ingestion complete. Summary:")
    print("=" * 60)
    for item in list_ingested():
        print(f"  {item['company']}: {item['chunks']} chunks from {item['files']}")


if __name__ == "__main__":
    main()
