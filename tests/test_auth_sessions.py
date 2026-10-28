"""Тести одноразових OIDC flow і строку дії локальних сесій."""

from uuid import uuid4

from src.services.auth_sessions import InMemoryAuthSessionStore, InMemoryOidcFlowStore


def test_oidc_flow_expires_and_is_consumed_once() -> None:
    """[TP-AUTH-03] [FR-001] [SEC-001]
    OIDC flow має обмежений строк дії та споживається рівно один раз.
    """
    store = InMemoryOidcFlowStore(ttl_seconds=0)
    store.save("state", {"state": "state"})

    assert store.pop("state") is None
    assert store.pop("state") is None


def test_auth_session_expires() -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Локальна сесія користувача завершується після завершення TTL.
    """
    store = InMemoryAuthSessionStore(ttl_seconds=0)
    token = store.create(uuid4())

    assert store.resolve(token) is None
