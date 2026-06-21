"""
qa.py — Conversational Q&A using OpenAI + retrieved context.

Flow per query:
  1. Retrieve top-K chunks for the query (access-controlled).
  2. Build a OpenAI messages payload:
       system  → role + strict grounding instructions
       history → past N turns from session.py
       user    → retrieved context block + current question
  3. Call OpenAI API and return the answer + source citations.
"""

import os
from openai import OpenAI
from backend.retrieval import retrieve
from backend import session as session_store

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1")
MAX_TOKENS = 1024

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()  # Automatically reads OPENAI_API_KEY
    return _client


SYSTEM_PROMPT = """You are a knowledgeable financial analyst assistant.

You answer questions strictly based on the document excerpts provided in each user message.
Rules:
- Only use information from the <context> block. Do NOT use outside knowledge.
- If the context does not contain enough information to answer, say so clearly.
- When you use a specific fact, mention the source company and page number.
- Keep answers concise and factual.
- For follow-up questions, use both the <context> and the earlier conversation turns.
"""


def answer(
    query: str,
    token: str,
    allowed_companies: list[str],
    top_k: int = 5,
) -> dict:
    """
    Generate a grounded answer for `query`.

    Returns:
        {
          "answer":  str,
          "sources": [{"company", "filename", "page_num", "score"}, ...],
        }
    """
    # 1. Retrieve relevant chunks (access-controlled)
    chunks = retrieve(query, allowed_companies, top_k=top_k)

    if not chunks:
        no_data = (
            "I couldn't find any relevant information in the documents "
            f"you have access to ({', '.join(allowed_companies)}). "
            "Please try rephrasing your question."
        )
        session_store.append_turn(token, query, no_data)
        return {"answer": no_data, "sources": []}

    # 2. Build context block for the model
    context_lines = []
    for i, chunk in enumerate(chunks, start=1):
        context_lines.append(
            f"[{i}] (Company: {chunk['company']} | File: {chunk['filename']} | Page: {chunk['page_num']})\n"
            f"{chunk['text']}"
        )
    context_block = "\n\n---\n\n".join(context_lines)

    # 3. Build messages array = history + new user turn
    history = session_store.get_history(token)

    user_turn_content = (
        f"<context>\n{context_block}\n</context>\n\n"
        f"Question: {query}"
    )

    messages = history + [{"role": "user", "content": user_turn_content}]

    # 4. Call OpenAI
    client = _get_client()
    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=SYSTEM_PROMPT,
        input=messages,
        max_output_tokens=MAX_TOKENS,
    )

    answer_text = response.output_text.strip()

    # 5. Persist turn to session history
    # Store the *raw* query (not the context-wrapped version) so history
    # is readable and doesn't balloon with repeated context blocks.
    session_store.append_turn(token, query, answer_text)

    # 6. Return answer + deduplicated source list
    seen = set()
    sources = []
    for chunk in chunks:
        key = (chunk["company"], chunk["filename"], chunk["page_num"])
        if key not in seen:
            seen.add(key)
            sources.append({
                "company":  chunk["company"],
                "filename": chunk["filename"],
                "page_num": chunk["page_num"],
                "score":    chunk["score"],
            })

    return {"answer": answer_text, "sources": sources}
