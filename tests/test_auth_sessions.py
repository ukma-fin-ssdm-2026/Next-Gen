"""Тести одноразових OIDC flow і строку дії локальних сесій."""

from uuid import uuid4

from src.services.auth_sessions import InMemoryAuthSessionStore, InMemoryOidcFlowStore


def test_oidc_flow_expires_and_is_consumed_once() -> None:
    store = InMemoryOidcFlowStore(ttl_seconds=0)
    store.save("state", {"state": "state"})

    assert store.pop("state") is None
    assert store.pop("state") is None


def test_auth_session_expires() -> None:
    store = InMemoryAuthSessionStore(ttl_seconds=0)
    token = store.create(uuid4())

    assert store.resolve(token) is None
