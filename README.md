# Multi-User Document Search & Conversational Q&A

A Python RAG application for querying earnings-call PDFs with server-enforced
document access control, per-session conversation history, and a Streamlit UI.

## Architecture

```text
Streamlit UI -> FastAPI -> ChromaDB
                         -> OpenAI API
```

| Component | Technology |
|---|---|
| Embeddings | OpenAI `text-embedding-3-small` |
| Vector database | ChromaDB (local persistent store) |
| Answer generation | OpenAI Responses API |
| PDF parsing | pdfplumber |
| Backend | FastAPI |
| Frontend | Streamlit |

## Included functionalities

- Email login for three users
- One- or two-company access per user
- Server-side company filtering during vector search
- Per-session conversational history and context-aware follow-up retrieval
- Isolated chat histories for simultaneous users
- Answer source metadata and retrieved excerpts
- Five sample Q4 2025 earnings-call PDFs
- Web UI for login, chat, source viewing, clearing chat, and logout

## Demo users

| User | Email | Accessible companies |
|---|---|---|
| Alice | `alice@email.com` | GOOGLE |
| Bob | `bob@email.com` | AMD, META |
| Charlie | `charlie@email.com` | MSFT, NFLX |

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Set your OpenAI API key:

   PowerShell:

   ```powershell
   $env:OPENAI_API_KEY="your-api-key"
   ```

   macOS/Linux:

   ```bash
   export OPENAI_API_KEY="your-api-key"
   ```

3. Ingest the sample PDFs:

   ```bash
   python ingest_all.py
   ```

   Ingestion calls the OpenAI embeddings API, so `OPENAI_API_KEY` must be set.
   The default embedding model is `text-embedding-3-small` with 1536
   dimensions.

4. Start the backend and check for status:

   ```bash
   python -m uvicorn main:app --reload --port 8000
   Invoke-RestMethod http://localhost:8000/health
   ```

5. In a second terminal, start the UI:

   ```bash
   python -m streamlit run frontend/app.py
   ```

6. Open `http://localhost:8501`.

## Optional configuration

```powershell
$env:OPENAI_MODEL="gpt-4.1"
$env:OPENAI_EMBEDDING_MODEL="text-embedding-3-small"
$env:OPENAI_EMBEDDING_DIMENSIONS="1536"
$env:API_BASE="http://localhost:8000"
```

If the embedding model or dimensions change, rerun `python ingest_all.py`.

## Sample documents

The `data/pdfs/` directory contains:

```text
Alphabet_Q4_2025.pdf
AMD_Q4_2025.pdf
META_Q4_2025.pdf
Microsoft_Q4_2025.pdf
Netflix_Q4_2025.pdf
```

Their company tags are configured in `ingest_all.py` and must match
`backend/auth.py`.

## Demo checklist

1. Log in as Alice and ask a question about Alphabet/Google revenue like "What was revenue in Q4?"
2. Log in as Bob in another browser session and query about Google like "What was revenue of Google in Q4 2025?"
3. Verify that Alice cannot retrieve Bob's company documents and vice versa.
4. Log in as Charlie, Ask "What were Microsoft's top 5 business highlights in FY25 Q4?" and few follow up questions like "Which one showed the strongest growth, and what factors did management say were driving it?" and "How does Microsoft's outlook for next quarter relate to that business area, and are there any constraints or risks mentioned?"
5. Expand Sources to show the authorized document, page, score, and excerpt.

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/login` | Authenticate a dummy email and create a session |
| POST | `/logout` | Invalidate the session |
| GET | `/me` | Return the current user |
| POST | `/query` | Retrieve authorized context and generate an answer |
| POST | `/clear-history` | Clear the current conversation |
| GET | `/ingestion-status` | List the user's authorized ingested documents |
| GET | `/health` | Health check |

Protected endpoints use the `X-Session-Token` header.
