"""
session.py — Per-user conversational session management.

Each session token maps to a rolling message history (list of
{role, content} dicts) that is passed to the OpenAI API,
giving the model full conversational context.

History is kept in-memory; for production I would back this with Redis.
"""

from typing import Optional

MAX_HISTORY_TURNS = 10   # keep last N user+assistant pairs (20 messages)

# token → list of {"role": "user"|"assistant", "content": str}
_histories: dict[str, list[dict]] = {}


def get_history(token: str) -> list[dict]:
    """Return the full message history for this session."""
    return _histories.get(token, [])


def append_turn(token: str, user_message: str, assistant_message: str) -> None:
    """
    Append one Q&A turn to the session history.
    Trims to the last MAX_HISTORY_TURNS turns to avoid unbounded growth.
    """
    history = _histories.setdefault(token, [])
    history.append({"role": "user",      "content": user_message})
    history.append({"role": "assistant", "content": assistant_message})

    # Trim: keep last MAX_HISTORY_TURNS turns = 2*MAX_HISTORY_TURNS messages
    max_messages = MAX_HISTORY_TURNS * 2
    if len(history) > max_messages:
        _histories[token] = history[-max_messages:]


def clear_history(token: str) -> None:
    """Reset the conversation for a session (e.g. user clicks 'New Chat')."""
    _histories.pop(token, None)


def session_exists(token: str) -> bool:
    return token in _histories
