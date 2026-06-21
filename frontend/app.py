"""
app.py — Streamlit UI for the Multi-User Document Q&A System.

Run with:
    streamlit run frontend/app.py
"""

import streamlit as st
import httpx
import os

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="DocuSearch Q&A",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
for key, default in [
    ("token", None),
    ("email", None),
    ("allowed_companies", []),
    ("messages", []),   # list of {role, content, sources}
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# Helper — API calls
# ---------------------------------------------------------------------------

def api_post(path: str, json: dict = None, headers: dict = None, **kwargs):
    try:
        r = httpx.post(f"{API_BASE}{path}", json=json, headers=headers or {}, timeout=60, **kwargs)
        return r
    except httpx.ConnectError:
        st.error("❌ Cannot reach the backend. Make sure the FastAPI server is running (`uvicorn main:app`).")
        st.stop()


def api_get(path: str, headers: dict = None):
    try:
        r = httpx.get(f"{API_BASE}{path}", headers=headers or {}, timeout=30)
        return r
    except httpx.ConnectError:
        st.error("❌ Cannot reach the backend. Make sure the FastAPI server is running (`uvicorn main:app`).")
        st.stop()


def auth_headers():
    return {"X-Session-Token": st.session_state.token}


# ---------------------------------------------------------------------------
# Login screen
# ---------------------------------------------------------------------------

def show_login():
    st.markdown(
        """
        <div style='text-align:center; padding: 3rem 0 1rem;'>
            <h1>📄 DocuSearch Q&A</h1>
            <p style='color:#666; font-size:1.1rem;'>
                Multi-user document search with access control
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            st.subheader("🔐 Sign In")
            st.caption("Use one of the demo accounts below:")

            # Quick-select buttons
            demo_users = {
                "Alice (GOOGL only)":        "alice@email.com",
                "Bob (AMD + META)":       "bob@email.com",
                "Charlie (MSFT + NFLX)":    "charlie@email.com",
            }
            for label, email in demo_users.items():
                if st.button(label, use_container_width=True, key=f"demo_{email}"):
                    _do_login(email)

            st.divider()
            email_input = st.text_input("Or enter email manually:", placeholder="user@email.com")
            if st.button("Sign In", type="primary", use_container_width=True):
                if email_input.strip():
                    _do_login(email_input.strip())
                else:
                    st.warning("Please enter an email address.")


def _do_login(email: str):
    r = api_post("/login", json={"email": email})
    if r.status_code == 200:
        data = r.json()
        st.session_state.token              = data["token"]
        st.session_state.email              = data["email"]
        st.session_state.allowed_companies  = data["allowed_companies"]
        st.session_state.messages           = []
        st.rerun()
    else:
        detail = r.json().get("detail", "Login failed")
        st.error(f"❌ {detail}")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def show_sidebar():
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.email}")
        st.markdown("**Accessible companies:**")
        for c in st.session_state.allowed_companies:
            st.markdown(f"- `{c}`")

        st.divider()

        # Ingestion status
        with st.expander("📦 Ingestion Status", expanded=False):
            r = api_get("/ingestion-status")
            if r.status_code == 200:
                items = r.json().get("ingested", [])
                if items:
                    for item in items:
                        st.markdown(f"**{item['company']}** — {item['chunks']} chunks")
                        for f in item["files"]:
                            st.caption(f"  • {f}")
                else:
                    st.info("No documents ingested yet.")

        st.divider()

        # Upload & ingest
        with st.expander("⬆️ Upload PDF (Admin)", expanded=False):
            company_tag = st.text_input("Company tag (e.g. AAPL)", key="ingest_company").upper()
            uploaded = st.file_uploader("Select PDF", type=["pdf"], key="ingest_file")
            if st.button("Ingest PDF", key="ingest_btn"):
                if uploaded and company_tag:
                    with st.spinner("Ingesting…"):
                        r = httpx.post(
                            f"{API_BASE}/ingest",
                            data={"company": company_tag},
                            files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
                            timeout=300,
                        )
                    if r.status_code == 200:
                        st.success(r.json()["message"])
                    else:
                        st.error(r.json().get("detail", "Ingestion failed"))
                else:
                    st.warning("Provide both a company tag and a PDF.")

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                api_post("/clear-history", headers=auth_headers())
                st.session_state.messages = []
                st.rerun()
        with col2:
            if st.button("🚪 Logout", use_container_width=True):
                api_post("/logout", headers=auth_headers())
                for key in ["token", "email", "allowed_companies", "messages"]:
                    st.session_state[key] = None if key == "token" else ([] if key in ["allowed_companies", "messages"] else None)
                st.rerun()


# ---------------------------------------------------------------------------
# Chat screen
# ---------------------------------------------------------------------------

def show_chat():
    st.title("📄 DocuSearch Q&A")
    st.caption(
        f"Logged in as **{st.session_state.email}** · "
        f"Access: {', '.join(st.session_state.allowed_companies)}"
    )

    # --- Render message history ---
    chat_container = st.container()
    with chat_container:
        if not st.session_state.messages:
            st.info(
                "👋 Ask me anything about the earnings call documents you have access to. "
                "I'll maintain context across follow-up questions."
            )

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                # Show source citations for assistant turns
                if msg["role"] == "assistant" and msg.get("sources"):
                    with st.expander(f"📚 Sources ({len(msg['sources'])} chunks)", expanded=False):
                        for src in msg["sources"]:
                            st.markdown(
                                f"**{src['company']}** · {src['filename']} · "
                                f"Page {src['page_num']} · "
                                f"Relevance: `{src['score']:.2%}`"
                            )

    # --- Input box ---
    if question := st.chat_input("Ask a question about the earnings calls…"):
        # Show user message immediately
        st.session_state.messages.append({"role": "user", "content": question, "sources": []})

        with st.chat_message("user"):
            st.markdown(question)

        # Call API
        with st.chat_message("assistant"):
            with st.spinner("Searching documents and generating answer…"):
                r = api_post(
                    "/query",
                    json={"question": question, "top_k": 5},
                    headers=auth_headers(),
                )

            if r.status_code == 200:
                data = r.json()
                answer_text = data["answer"]
                sources = data.get("sources", [])

                st.markdown(answer_text)

                if sources:
                    with st.expander(f"📚 Sources ({len(sources)} chunks)", expanded=False):
                        for src in sources:
                            st.markdown(
                                f"**{src['company']}** · {src['filename']} · "
                                f"Page {src['page_num']} · "
                                f"Relevance: `{src['score']:.2%}`"
                            )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer_text,
                    "sources": sources,
                })
            else:
                err = r.json().get("detail", "Unknown error")
                st.error(f"❌ {err}")


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

if st.session_state.token is None:
    show_login()
else:
    show_sidebar()
    show_chat()
