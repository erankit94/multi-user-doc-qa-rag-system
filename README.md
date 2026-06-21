# 📄 Multi-User Document Search & Conversational Q&A System

A RAG (Retrieval-Augmented Generation) system that lets multiple users query earnings-call PDFs through a chat UI, with **server-enforced document access control** and **per-user conversational memory**.

---

## Architecture

```
Streamlit UI  ──►  FastAPI Backend  ──►  ChromaDB (vector store)
                        │
                        ▼
                  Claude API (claude-sonnet-4-6)
```

| Component | Technology |
|---|---|
| Embeddings | `sentence-transformers` (all-MiniLM-L6-v2, runs locally) |
| Vector DB | ChromaDB (local persistent store) |
| LLM | Anthropic Claude (claude-sonnet-4-6) |
| PDF parsing | pdfplumber (text + tables) |
| Backend API | FastAPI |
| Frontend UI | Streamlit |

---

## Project Structure

```
rag_system/
├── backend/
│   ├── auth.py        # User → company access map + session tokens
│   ├── ingest.py      # PDF → chunks → embeddings → ChromaDB
│   ├── retrieval.py   # Vector search with company-level filter
│   ├── session.py     # Per-user conversation history
│   └── qa.py          # Claude API call (RAG + history)
├── frontend/
│   └── app.py         # Streamlit chat UI
├── data/
│   └── pdfs/          # ← put your earnings-call PDFs here
├── chroma_db/         # Auto-created on first ingest
├── main.py            # FastAPI app entry point
├── ingest_all.py      # One-shot ingestion script
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Clone & install dependencies

```bash
git clone <your-repo-url>
cd rag_system
pip install -r requirements.txt
```

### 2. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. Add your earnings-call PDFs

Copy your Q4 2025 earnings-call transcript PDFs into `data/pdfs/`:

```
data/pdfs/
├── AAPL_Q4_2025.pdf
├── GOOGL_Q4_2025.pdf
├── MSFT_Q4_2025.pdf
├── AMZN_Q4_2025.pdf
└── META_Q4_2025.pdf
```

> **Filename format:** `<COMPANY_TAG>_Q4_2025.pdf`  
> The company tag must match the tags in `backend/auth.py` → `USER_ACCESS`.

### 4. Ingest the PDFs

```bash
python ingest_all.py
```

This parses each PDF, splits it into ~500-word chunks, embeds them with a local model, and stores them in ChromaDB. **Run once.** Re-running is idempotent (upsert).

### 5. Start the FastAPI backend

```bash
uvicorn main:app --reload --port 8000
```

### 6. Start the Streamlit frontend (new terminal)

```bash
streamlit run frontend/app.py
```

Open http://localhost:8501 in your browser.

---

## Demo Users

| User | Email | Accessible Companies |
|---|---|---|
| Alice | `alice@email.com` | AAPL |
| Bob | `bob@email.com` | GOOGL, MSFT |
| Charlie | `charlie@email.com` | AMZN, META |

---

## How to Demo

### 1. Access isolation
1. Log in as **Alice** → ask *"What was the revenue in Q4?"*  
   → Returns only AAPL data.
2. Log out → log in as **Bob** → ask the same question  
   → Returns only GOOGL/MSFT data. Alice's AAPL docs are invisible.

### 2. Conversational follow-up
1. Log in as **Bob**, ask *"What was Microsoft's operating income in Q4 2025?"*
2. Follow up: *"How does that compare to the previous quarter?"*  
   → The system uses the earlier answer as context.
3. Follow up: *"What did the CFO say about margins?"*  
   → Still remembers the thread.

### 3. Query isolation across users
- Open two browser tabs (use incognito for one).  
- Log in as different users simultaneously.  
- Their conversation histories and document access are completely independent.

---

## Key Design Decisions

### 1. Access control is server-enforced
The ChromaDB `where` filter (`{"company": {"$in": allowed_companies}}`) is applied **inside the database layer**, not in the application layer. A user cannot retrieve chunks from unauthorised companies even if they manipulate the query.

### 2. Overlapping chunks prevent cut-off answers
Chunks are 500 words with an 80-word overlap. This ensures that answers spanning a page boundary are captured in at least one chunk.

### 3. Context-injected prompting
Each Claude call receives:
- A strict system prompt instructing it to use only the provided context
- The last 10 conversation turns (sliding window)
- The retrieved chunks wrapped in `<context>` tags

### 4. Stateless retrieval, stateful conversation
Retrieval is fresh per query (the best chunks for *this* question). The LLM sees the conversation history to maintain context. The two concerns are separated.

### 5. Tables are handled
`pdfplumber` extracts both body text and tables. Tables are serialised as tab-separated rows so the LLM can reason over financial figures without special handling.

---

## Adding More Users or Companies

Edit `backend/auth.py`:

```python
USER_ACCESS = {
    "alice@email.com":   ["AAPL"],
    "bob@email.com":     ["GOOGL", "MSFT"],
    "charlie@email.com": ["AMZN", "META"],
    # Add more users here ↓
    "david@email.com":   ["NVDA"],
}
```

Then ingest the new PDF:

```bash
python -c "
from backend.ingest import ingest_pdf
ingest_pdf('data/pdfs/NVDA_Q4_2025.pdf', 'NVDA')
"
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/login` | `{"email": "..."}` → session token |
| POST | `/logout` | Invalidate token |
| GET | `/me` | Current user info |
| POST | `/query` | `{"question": "..."}` → answer + sources |
| POST | `/clear-history` | Reset conversation |
| GET | `/ingestion-status` | What's in ChromaDB |
| POST | `/ingest` | Upload + ingest a PDF (admin) |

All protected endpoints require the `X-Session-Token` header.

Interactive docs: http://localhost:8000/docs
