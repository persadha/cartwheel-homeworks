"""Homework 2, Part D: authentication tests for the session endpoints.

Everything here runs offline. The route functions are called as plain Python
functions rather than through FastAPI's TestClient, because TestClient runs the
lifespan hook in server/app.py, which calls setup_tracing() and reaches for
Langfuse. The handout requires these tests to pass without Langfuse, Docker, or
a model provider key.

The session-scoped `world` fixture points CARTWHEEL_DB at a throwaway seeded
database, so nothing here touches data/. In that world users 1 and 2 are
shoppers and user 9002 is a merchant at store 2.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from server import app as server_app


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    """_SESSIONS is module-level state; start every test from empty."""
    server_app._SESSIONS.clear()


def test_create_session_rejects_role_mismatch(world: dict) -> None:
    """A claimed role that differs from the stored role is refused."""
    with pytest.raises(HTTPException) as excinfo:
        server_app.create_session(
            server_app.SessionCreate(user_id=9002, role="support")
        )

    assert excinfo.value.status_code == 403
    # Nothing was registered, so the check ran before any token was issued.
    assert server_app._SESSIONS == {}


def test_token_cannot_authorize_another_session(world: dict) -> None:
    """A token is bound to the one session it was issued for."""
    first = server_app.create_session(
        server_app.SessionCreate(user_id=1, role="shopper")
    )
    second = server_app.create_session(
        server_app.SessionCreate(user_id=2, role="shopper")
    )

    # Assert the token is well formed first, so the refusal below is provably
    # about session binding rather than a bad signature.
    assert server_app.verify_token(first["token"]) is not None

    with pytest.raises(HTTPException) as excinfo:
        server_app._authorize(second["session_id"], "Bearer " + first["token"])
    assert excinfo.value.status_code == 403

    # Positive control: the same token still authorizes its own session.
    ctx = server_app._authorize(first["session_id"], "Bearer " + first["token"])
    assert ctx.user_id == 1
    assert ctx.role == "shopper"
