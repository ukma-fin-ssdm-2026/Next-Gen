"""Наскрізні HTTP-тести та тести безпеки/polling для чату (ADR-005).

Покриває ендпоінти `/api/v1/listings/{id}/conversation` і `/api/v1/conversations*`:
автентифікацію, IDOR (`SEC-003`), конфіденційність контактів (`SEC-002`),
блокування користувачів (`FR-013`), курсорну пагінацію, валідацію тексту,
сервісні ліміти `429` із `Retry-After`, картку знятого оголошення,
аудит `CONVERSATION_STARTED` (`FR-018`) та вимоги polling (`PERF-002`).
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import logging
import math
import statistics
import time
from uuid import UUID, uuid4

import httpx
import pytest

from src.api.deps import (
    SESSION_COOKIE_NAME,
    get_activity_service,
    get_auth_service,
    get_auth_session_store,
    get_conversation_service,
    get_user_repository,
)
from src.api.main import app
from src.domain.conversations import ChatSettings, Message
from src.domain.listings import SEED_CATEGORY_ID, SEED_IMAGE_URL, Listing, ListingImage
from src.domain.users import CurrentUser, User, UserRole
from src.repositories.conversations import InMemoryConversationRepository
from src.repositories.listings import InMemoryListingRepository
from src.repositories.moderation import InMemoryModerationActionRepository
from src.repositories.support import InMemoryActivityRepository
from src.repositories.users import InMemoryUserRepository
from src.services.activity import ActivityLogService
from src.services.auth import AuthService, EntraAuthConfig
from src.services.auth_sessions import InMemoryAuthSessionStore
from src.services.conversations import ConversationService

API = "/api/v1"
T0 = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
CHAT_BENCHMARK_ROUNDS = 3
CHAT_WARMUP_REQUESTS = 3


@dataclass
class ChatEnv:
    """Ізольоване тестове середовище чату зі змінним годинником і сесіями."""

    users: InMemoryUserRepository
    listings: InMemoryListingRepository
    conversations: InMemoryConversationRepository
    sessions: InMemoryAuthSessionStore
    now: list[datetime]
    settings: list[ChatSettings]

    def advance(self, seconds: float = 0, microseconds: int = 0) -> datetime:
        self.now[0] = self.now[0] + timedelta(
            seconds=seconds, microseconds=microseconds
        )
        return self.now[0]

    def make_user(
        self,
        *,
        display_name: str,
        email: str,
        contact: str | None = None,
        avatar_url: str | None = None,
        role: UserRole = UserRole.USER,
        is_blocked: bool = False,
        user_id: UUID | None = None,
    ) -> User:
        user = User(
            user_id=user_id or uuid4(),
            tenant_id=uuid4(),
            entra_object_id=uuid4(),
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            contact=contact,
            role=role,
            is_blocked=is_blocked,
        )
        return self.users.save(user)

    def authenticate(self, client, user: User) -> str:
        token = self.sessions.create(user.user_id)
        client.cookies.set(SESSION_COOKIE_NAME, token)
        return token

    def add_listing(
        self,
        owner: User,
        *,
        title: str = "Підручник з матаналізу",
        price: float = 250.0,
        contact: str = "@seller_hidden_tg",
        image_url: str = SEED_IMAGE_URL,
    ) -> Listing:
        listing = Listing(
            id=uuid4(),
            title=title,
            description="Стан добрий, без поміток.",
            price=price,
            category_id=SEED_CATEGORY_ID,
            contact=contact,
            user_id=owner.user_id,
            images=[ListingImage(image_url=image_url, display_order=0)],
        )
        return self.listings.save(listing)


@pytest.fixture
def chat_env(client, login_as, listing_repository, monkeypatch) -> ChatEnv:
    """Налаштовує ізольований `ConversationService` для HTTP-тестів чату."""
    users = app.dependency_overrides[get_user_repository]()
    activity = app.dependency_overrides[get_activity_service]()
    sessions = app.dependency_overrides[get_auth_session_store]()
    repo = InMemoryConversationRepository()
    clock_box = [T0]
    settings_box = [ChatSettings()]

    def _service_factory() -> ConversationService:
        return ConversationService(
            repo,
            listing_repository,
            users,
            activity,
            settings_box[0],
            clock=lambda: clock_box[0],
        )

    monkeypatch.setitem(
        app.dependency_overrides, get_conversation_service, _service_factory
    )
    return ChatEnv(
        users=users,
        listings=listing_repository,
        conversations=repo,
        sessions=sessions,
        now=clock_box,
        settings=settings_box,
    )


def _assert_no_secrets(payload_text: str, secrets: tuple[str, ...]) -> None:
    """Переконується, що жоден чутливий рядок не потрапив у відповідь чи логи."""
    for secret in secrets:
        assert secret not in payload_text, f"Витік конфіденційних даних: {secret!r}"


def _all_keys(obj: object) -> set[str]:
    """Збирає всі імена JSON-ключів рекурсивно."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.add(str(key))
            keys.update(_all_keys(value))
    elif isinstance(obj, list):
        for item in obj:
            keys.update(_all_keys(item))
    return keys


# ---------------------------------------------------------------------------
# Автентифікація, підміна актора та блокування
# ---------------------------------------------------------------------------


def test_anonymous_gets_401_on_every_chat_endpoint(client, chat_env: ChatEnv) -> None:
    """[TP-055] [FR-021] [FR-022] [SEC-001] [SEC-003]
    Анонім і запити лише з фейковими заголовками отримують 401 на всіх 6 маршрутах.
    """
    seller = chat_env.make_user(
        display_name="Продавець",
        email="seller1@ukma.edu.ua",
        contact="@seller_secret",
    )
    listing = chat_env.add_listing(seller, contact="@listing_secret")
    conv_id = uuid4()

    calls: list[Callable[[dict[str, str]], object]] = [
        lambda h: client.post(
            f"{API}/listings/{listing.id}/conversation",
            json={"body": "Привіт"},
            headers=h,
        ),
        lambda h: client.get(f"{API}/conversations", headers=h),
        lambda h: client.get(f"{API}/conversations/unread-count", headers=h),
        lambda h: client.get(f"{API}/conversations/{conv_id}/messages", headers=h),
        lambda h: client.post(
            f"{API}/conversations/{conv_id}/messages",
            json={"body": "Привіт"},
            headers=h,
        ),
        lambda h: client.post(f"{API}/conversations/{conv_id}/read", headers=h),
    ]

    for make_call in calls:
        anon_res = make_call({})
        assert anon_res.status_code == 401
        assert anon_res.headers.get("cache-control") == "no-store"
        spoofed_res = make_call(
            {"X-Actor-Id": str(seller.user_id), "X-Actor-Role": "ADMIN"}
        )
        assert spoofed_res.status_code == 401
        assert spoofed_res.headers.get("cache-control") == "no-store"

        client.cookies.set(SESSION_COOKIE_NAME, "forged-session-token")
        forged_res = make_call({})
        assert forged_res.status_code == 401
        assert forged_res.headers.get("cache-control") == "no-store"
        client.cookies.clear()


@pytest.mark.parametrize(
    "extra_field", ["sender_id", "user_id", "email", "role", "owner_id"]
)
def test_client_identity_fields_in_body_are_rejected_with_422(
    client, chat_env: ChatEnv, extra_field: str
) -> None:
    """[TP-055] [SEC-001] [SEC-003]
    Клієнтські поля ідентичності й ролі в тілі запиту заборонені (extra=forbid -> 422).
    """
    seller = chat_env.make_user(
        display_name="Продавець", email="seller.forbid@ukma.edu.ua"
    )
    buyer = chat_env.make_user(
        display_name="Покупець", email="buyer.forbid@ukma.edu.ua"
    )
    listing = chat_env.add_listing(seller)

    chat_env.authenticate(client, buyer)
    start_res = client.post(
        f"{API}/listings/{listing.id}/conversation",
        json={"body": "Добрий день", extra_field: str(seller.user_id)},
    )
    assert start_res.status_code == 422
    assert start_res.headers.get("cache-control") == "no-store"

    ok = client.post(
        f"{API}/listings/{listing.id}/conversation",
        json={"body": "Початок розмови"},
    )
    assert ok.status_code == 201
    conv_id = ok.json()["conversation_id"]

    msg_res = client.post(
        f"{API}/conversations/{conv_id}/messages",
        json={"body": "Ще одне", extra_field: "ADMIN"},
    )
    assert msg_res.status_code == 422
    assert msg_res.headers.get("cache-control") == "no-store"

    invalid_uuid = client.get(f"{API}/conversations/not-a-uuid/messages")
    assert invalid_uuid.status_code == 422
    assert invalid_uuid.headers.get("cache-control") == "no-store"


def test_blocked_user_cannot_use_any_chat_endpoint(client, chat_env: ChatEnv) -> None:
    """[TP-055] [FR-021] [FR-022] [SEC-001] [SEC-003]
    Заблокований користувач отримує 403 на кожному з 6 ендпоінтів чату.
    """
    seller = chat_env.make_user(
        display_name="Продавець", email="seller.blk@ukma.edu.ua"
    )
    buyer = chat_env.make_user(display_name="Покупець", email="buyer.blk@ukma.edu.ua")
    listing = chat_env.add_listing(seller)

    chat_env.authenticate(client, buyer)
    started = client.post(
        f"{API}/listings/{listing.id}/conversation",
        json={"body": "Чи ще є в наявності?"},
    )
    assert started.status_code == 201
    conv_id = started.json()["conversation_id"]

    # Блокуємо покупця і перед кожним викликом видаємо нову cookie,
    # бо require_current_user відкликає використану сесію після першого 403.
    chat_env.users.save(replace(buyer, is_blocked=True))

    checks: list[Callable[[], object]] = [
        lambda: client.post(
            f"{API}/listings/{listing.id}/conversation",
            json={"body": "Спроба"},
        ),
        lambda: client.get(f"{API}/conversations"),
        lambda: client.get(f"{API}/conversations/unread-count"),
        lambda: client.get(f"{API}/conversations/{conv_id}/messages"),
        lambda: client.post(
            f"{API}/conversations/{conv_id}/messages",
            json={"body": "Спроба"},
        ),
        lambda: client.post(f"{API}/conversations/{conv_id}/read"),
    ]
    for call in checks:
        chat_env.authenticate(client, buyer)
        res = call()
        assert res.status_code == 403
        assert res.headers.get("cache-control") == "no-store"


# ---------------------------------------------------------------------------
# Старт розмови, ідемпотентність пари, self-chat та картка оголошення
# ---------------------------------------------------------------------------


def test_start_conversation_201_then_200_self_chat_and_audit(
    client, chat_env: ChatEnv
) -> None:
    """[TP-055] [FR-021] [FR-018] [SEC-002] [SEC-003]
    Старт створює розмову (201), повторний старт повертає 200 без дубля,
    власник не може писати собі (403), а перше повідомлення є обов'язковим (422).
    """
    seller = chat_env.make_user(
        display_name="Олена Продавець",
        email="olena.secret@ukma.edu.ua",
        contact="@olena_profile_secret",
        avatar_url="/uploads/olena.webp",
    )
    buyer = chat_env.make_user(
        display_name="Тарас Покупець",
        email="taras.secret@ukma.edu.ua",
        contact="+380991112233",
        avatar_url="/uploads/taras.webp",
    )
    listing_one = chat_env.add_listing(
        seller, title="Калькулятор Casio", price=300.0, contact="@listing_tg_secret"
    )
    listing_two = chat_env.add_listing(
        seller, title="Зошит у клітинку", price=50.0, contact="@listing2_secret"
    )
    buyer_listing = chat_env.add_listing(
        buyer, title="Рюкзак", price=700.0, contact="@buyer_listing_secret"
    )

    secrets = (
        seller.email,
        seller.contact or "",
        buyer.email,
        buyer.contact or "",
        listing_one.contact,
        listing_two.contact,
        buyer_listing.contact,
    )

    # Власник не може почати розмову із собою (403).
    chat_env.authenticate(client, seller)
    self_res = client.post(
        f"{API}/listings/{listing_one.id}/conversation",
        json={"body": "Напишу собі"},
    )
    assert self_res.status_code == 403
    assert self_res.headers.get("cache-control") == "no-store"

    # Перше повідомлення обов'язкове (відсутнє, порожнє або лише з пробілів -> 422).
    chat_env.authenticate(client, buyer)
    missing_body = client.post(f"{API}/listings/{listing_one.id}/conversation", json={})
    assert missing_body.status_code == 422
    assert missing_body.headers.get("cache-control") == "no-store"
    for empty_body in ("", "   "):
        bad = client.post(
            f"{API}/listings/{listing_one.id}/conversation",
            json={"body": empty_body},
        )
        assert bad.status_code == 422
        assert bad.headers.get("cache-control") == "no-store"
    assert (
        chat_env.conversations.get_by_pair(*sorted((buyer.user_id, seller.user_id)))
        is None
    )

    # Перший старт -> 201 Created.
    secret_first_msg = "Добрий день! Калькулятор ще є?"
    created = client.post(
        f"{API}/listings/{listing_one.id}/conversation",
        json={"body": f"  {secret_first_msg}  "},
    )
    assert created.status_code == 201
    assert created.headers["cache-control"] == "no-store"
    created_data = created.json()
    assert created_data["created"] is True
    conv_id = created_data["conversation_id"]
    msg1 = created_data["message"]
    assert msg1["body"] == secret_first_msg
    assert msg1["is_own"] is True
    assert msg1["sender_id"] == str(buyer.user_id)
    assert msg1["listing"] == {
        "listing_id": str(listing_one.id),
        "available": True,
        "title": "Калькулятор Casio",
        "price": 300.0,
        "image_url": SEED_IMAGE_URL,
    }
    _assert_no_secrets(created.text, secrets)
    assert {"email", "contact"}.isdisjoint(_all_keys(created_data))

    # Повторний старт із іншого оголошення продавця -> 200 і та сама розмова.
    chat_env.advance(seconds=5)
    second = client.post(
        f"{API}/listings/{listing_two.id}/conversation",
        json={"body": "І ще про зошит хочу уточнити"},
    )
    assert second.status_code == 200
    assert second.headers["cache-control"] == "no-store"
    second_data = second.json()
    assert second_data["created"] is False
    assert second_data["conversation_id"] == conv_id
    assert second_data["message"]["listing"]["listing_id"] == str(listing_two.id)

    # Старт у зворотному напрямку (продавець зі сторінки оголошення покупця) -> 200.
    chat_env.advance(seconds=5)
    chat_env.authenticate(client, seller)
    reverse = client.post(
        f"{API}/listings/{buyer_listing.id}/conversation",
        json={"body": "Вітаю, цікавить рюкзак"},
    )
    assert reverse.status_code == 200
    assert reverse.json()["created"] is False
    assert reverse.json()["conversation_id"] == conv_id
    assert (
        chat_env.conversations.count_conversations_started_since(
            buyer.user_id, T0 - timedelta(minutes=1)
        )
        == 1
    )

    # Подія CONVERSATION_STARTED у журналі дій без тексту повідомлення.
    admin = chat_env.make_user(
        display_name="Адмін",
        email="admin.chat@ukma.edu.ua",
        role=UserRole.ADMIN,
    )
    chat_env.authenticate(client, admin)
    logs_res = client.get(f"{API}/admin/logs/users")
    assert logs_res.status_code == 200
    chat_logs = [
        entry
        for entry in logs_res.json()
        if entry["action_type"] == "CONVERSATION_STARTED"
    ]
    assert len(chat_logs) == 1
    assert chat_logs[0]["listing_id"] == str(listing_one.id)
    assert secret_first_msg not in str(chat_logs[0])


# ---------------------------------------------------------------------------
# IDOR, невідомі ресурси, чужі/зняті оголошення та картка знятого оголошення
# ---------------------------------------------------------------------------


def test_idor_non_participant_and_unknown_conversation_return_identical_404(
    client, chat_env: ChatEnv
) -> None:
    """[TP-055] [SEC-003]
    Не-учасник (зокрема ADMIN) і неіснуючий UUID отримують однаковий 404 без деталей.
    """
    seller = chat_env.make_user(display_name="Продавець", email="s.idor@ukma.edu.ua")
    buyer = chat_env.make_user(display_name="Покупець", email="b.idor@ukma.edu.ua")
    outsider = chat_env.make_user(display_name="Сторонній", email="o.idor@ukma.edu.ua")
    admin = chat_env.make_user(
        display_name="Адмін",
        email="a.idor@ukma.edu.ua",
        role=UserRole.ADMIN,
    )
    listing = chat_env.add_listing(seller)

    chat_env.authenticate(client, buyer)
    conv_id = client.post(
        f"{API}/listings/{listing.id}/conversation",
        json={"body": "Приватний текст"},
    ).json()["conversation_id"]
    unknown_id = str(uuid4())

    for intruder in (outsider, admin):
        chat_env.authenticate(client, intruder)

        get_foreign = client.get(f"{API}/conversations/{conv_id}/messages")
        get_unknown = client.get(f"{API}/conversations/{unknown_id}/messages")
        assert get_foreign.status_code == 404
        assert get_unknown.status_code == 404
        assert get_foreign.headers.get("cache-control") == "no-store"
        assert get_unknown.headers.get("cache-control") == "no-store"
        assert get_foreign.json() == get_unknown.json()
        assert "Приватний текст" not in get_foreign.text

        post_foreign = client.post(
            f"{API}/conversations/{conv_id}/messages", json={"body": "Втручання"}
        )
        post_unknown = client.post(
            f"{API}/conversations/{unknown_id}/messages", json={"body": "Втручання"}
        )
        assert post_foreign.status_code == 404
        assert post_unknown.status_code == 404
        assert post_foreign.headers.get("cache-control") == "no-store"
        assert post_unknown.headers.get("cache-control") == "no-store"
        assert post_foreign.json() == post_unknown.json()

        read_foreign = client.post(f"{API}/conversations/{conv_id}/read")
        read_unknown = client.post(f"{API}/conversations/{unknown_id}/read")
        assert read_foreign.status_code == 404
        assert read_unknown.status_code == 404
        assert read_foreign.headers.get("cache-control") == "no-store"
        assert read_unknown.headers.get("cache-control") == "no-store"
        assert read_foreign.json() == read_unknown.json()


def test_attach_listing_validation_and_withdrawn_listing_card_privacy(
    client, chat_env: ChatEnv
) -> None:
    """[TP-055] [FR-021] [FR-022] [SEC-002] [SEC-003]
    Чуже, зняте або неіснуюче оголошення дають однаковий 404; зняття оголошення
    після прикріплення перетворює картку на недоступну без контакту й назви.
    """
    seller = chat_env.make_user(
        display_name="Продавець",
        email="s.card@ukma.edu.ua",
        contact="@s_card_profile",
    )
    buyer = chat_env.make_user(display_name="Покупець", email="b.card@ukma.edu.ua")
    third_party = chat_env.make_user(
        display_name="Третій", email="t.card@ukma.edu.ua", contact="@third_secret"
    )
    active_listing = chat_env.add_listing(
        seller, title="Лампа настільна", price=420.0, contact="@active_tg_secret"
    )
    second_own_listing = chat_env.add_listing(
        seller, title="Степлер", price=60.0, contact="@stapler_secret"
    )
    foreign_listing = chat_env.add_listing(
        third_party, title="Чужий товар", price=999.0, contact="@foreign_tg_secret"
    )
    withdrawn_before_send = chat_env.add_listing(
        seller, title="Знятий товар", price=123.0, contact="@withdrawn_tg_secret"
    )

    chat_env.authenticate(client, seller)
    assert (
        client.delete(f"{API}/listings/{withdrawn_before_send.id}").status_code == 204
    )

    # Старт із знятого або неіснуючого оголошення -> однаковий 404.
    chat_env.authenticate(client, buyer)
    start_withdrawn = client.post(
        f"{API}/listings/{withdrawn_before_send.id}/conversation",
        json={"body": "Привіт"},
    )
    start_missing = client.post(
        f"{API}/listings/{uuid4()}/conversation",
        json={"body": "Привіт"},
    )
    assert start_withdrawn.status_code == 404
    assert start_missing.status_code == 404
    assert start_withdrawn.headers.get("cache-control") == "no-store"
    assert start_missing.headers.get("cache-control") == "no-store"
    assert start_withdrawn.json() == start_missing.json()

    # Створюємо розмову з активного оголошення.
    created = client.post(
        f"{API}/listings/{active_listing.id}/conversation",
        json={"body": "Цікавить лампа"},
    )
    assert created.status_code == 201
    conv_id = created.json()["conversation_id"]

    # Спроба прикріпити чуже, зняте або неіснуюче оголошення -> однаковий 404.
    bad_foreign = client.post(
        f"{API}/conversations/{conv_id}/messages",
        json={"body": "Гляньте це", "listing_id": str(foreign_listing.id)},
    )
    bad_withdrawn = client.post(
        f"{API}/conversations/{conv_id}/messages",
        json={"body": "Гляньте це", "listing_id": str(withdrawn_before_send.id)},
    )
    bad_missing = client.post(
        f"{API}/conversations/{conv_id}/messages",
        json={"body": "Гляньте це", "listing_id": str(uuid4())},
    )
    assert (
        bad_foreign.status_code,
        bad_withdrawn.status_code,
        bad_missing.status_code,
    ) == (
        404,
        404,
        404,
    )
    assert bad_foreign.headers.get("cache-control") == "no-store"
    assert bad_withdrawn.headers.get("cache-control") == "no-store"
    assert bad_missing.headers.get("cache-control") == "no-store"
    assert bad_foreign.json() == bad_withdrawn.json() == bad_missing.json()
    _assert_no_secrets(
        bad_foreign.text + bad_withdrawn.text,
        ("@foreign_tg_secret", "@withdrawn_tg_secret", "Чужий товар"),
    )

    # Прикріплення іншого ACTIVE оголошення учасника працює.
    chat_env.advance(seconds=1)
    attached = client.post(
        f"{API}/conversations/{conv_id}/messages",
        json={"body": "Ще степлер є?", "listing_id": str(second_own_listing.id)},
    )
    assert attached.status_code == 201
    assert attached.json()["listing"]["available"] is True

    # Знімаємо active_listing з публікації: історія розмови зберігається,
    # але картка показує лише available=False без назви, фото, ціни та контакту.
    chat_env.authenticate(client, seller)
    assert client.delete(f"{API}/listings/{active_listing.id}").status_code == 204

    chat_env.authenticate(client, buyer)
    history = client.get(f"{API}/conversations/{conv_id}/messages")
    assert history.status_code == 200
    assert history.headers["cache-control"] == "no-store"
    first_item = history.json()["items"][0]
    assert first_item["body"] == "Цікавить лампа"
    assert first_item["listing"] == {
        "listing_id": str(active_listing.id),
        "available": False,
        "title": None,
        "price": None,
        "image_url": None,
    }
    _assert_no_secrets(
        history.text,
        ("Лампа настільна", "@active_tg_secret", "@s_card_profile", seller.email),
    )

    conv_list = client.get(f"{API}/conversations")
    assert conv_list.status_code == 200
    assert conv_list.headers["cache-control"] == "no-store"
    other = conv_list.json()["items"][0]["other"]
    assert other == {
        "user_id": str(seller.user_id),
        "display_name": "Продавець",
        "avatar_url": None,
    }
    assert {"email", "contact"}.isdisjoint(_all_keys(conv_list.json()))


# ---------------------------------------------------------------------------
# Непрочитані, /read, курсори, однакові timestamps і cache headers
# ---------------------------------------------------------------------------


def test_unread_count_changes_after_read_and_cache_control(
    client, chat_env: ChatEnv
) -> None:
    """[TP-055] [FR-022] [SEC-002] [SEC-003]
    Лічильник непрочитаних зростає в отримувача, обнуляється після POST /read,
    а всі приватні GET-відповіді містять `Cache-Control: no-store`.
    """
    seller = chat_env.make_user(
        display_name="Продавець Іван",
        email="ivan.read@ukma.edu.ua",
        avatar_url="/uploads/ivan.webp",
    )
    buyer = chat_env.make_user(
        display_name="Покупець Марія",
        email="maria.read@ukma.edu.ua",
    )
    listing = chat_env.add_listing(seller)

    chat_env.authenticate(client, buyer)
    start_res = client.post(
        f"{API}/listings/{listing.id}/conversation",
        json={"body": "Перше питання"},
    )
    assert start_res.status_code == 201
    conv_id = start_res.json()["conversation_id"]

    chat_env.advance(seconds=1)
    assert (
        client.post(
            f"{API}/conversations/{conv_id}/messages",
            json={"body": "Друге питання"},
        ).status_code
        == 201
    )

    # У відправника (buyer) немає непрочитаних власних повідомлень.
    buyer_unread = client.get(f"{API}/conversations/unread-count")
    assert buyer_unread.status_code == 200
    assert buyer_unread.headers["cache-control"] == "no-store"
    assert buyer_unread.json() == {"unread_count": 0}

    # У співрозмовника (seller) обидва повідомлення непрочитані.
    chat_env.authenticate(client, seller)
    seller_unread = client.get(f"{API}/conversations/unread-count")
    assert seller_unread.status_code == 200
    assert seller_unread.headers["cache-control"] == "no-store"
    assert seller_unread.json() == {"unread_count": 2}

    seller_list = client.get(f"{API}/conversations")
    assert seller_list.status_code == 200
    assert seller_list.headers["cache-control"] == "no-store"
    assert seller_list.json()["items"][0]["unread_count"] == 2
    assert seller_list.json()["items"][0]["last_message"]["is_own"] is False

    # Після POST /read (204) лічильник обнуляється лише для читача.
    read_res = client.post(f"{API}/conversations/{conv_id}/read")
    assert read_res.status_code == 204
    assert read_res.content == b""
    assert read_res.headers["cache-control"] == "no-store"

    assert client.get(f"{API}/conversations/unread-count").json() == {"unread_count": 0}
    assert client.get(f"{API}/conversations").json()["items"][0]["unread_count"] == 0

    # Продавець відповідає -> у покупця unread_count стає 1, у продавця 0.
    chat_env.advance(seconds=1)
    reply_res = client.post(
        f"{API}/conversations/{conv_id}/messages",
        json={"body": "Так, актуально"},
    )
    assert reply_res.status_code == 201
    assert client.get(f"{API}/conversations/unread-count").json() == {"unread_count": 0}

    chat_env.authenticate(client, buyer)
    assert client.get(f"{API}/conversations/unread-count").json() == {"unread_count": 1}


def test_read_through_cursor_does_not_acknowledge_message_received_later(
    client, chat_env: ChatEnv
) -> None:
    """[TP-055] `/read` не підтверджує повідомлення новіше за показаний курсор."""
    seller = chat_env.make_user(
        display_name="Продавець",
        email="seller.cursor@ukma.edu.ua",
    )
    buyer = chat_env.make_user(
        display_name="Покупець",
        email="buyer.cursor@ukma.edu.ua",
    )
    listing = chat_env.add_listing(seller)

    chat_env.authenticate(client, buyer)
    started = client.post(
        f"{API}/listings/{listing.id}/conversation", json={"body": "m0"}
    )
    conversation_id = started.json()["conversation_id"]

    chat_env.authenticate(client, seller)
    shown = client.get(f"{API}/conversations/{conversation_id}/messages").json()
    shown_cursor = shown["after_cursor"]

    chat_env.authenticate(client, buyer)
    chat_env.advance(seconds=1)
    assert (
        client.post(
            f"{API}/conversations/{conversation_id}/messages", json={"body": "m1"}
        ).status_code
        == 201
    )

    chat_env.authenticate(client, seller)
    invalid = client.post(
        f"{API}/conversations/{conversation_id}/read",
        params={"through": "%%%"},
    )
    assert invalid.status_code == 422
    assert invalid.headers["cache-control"] == "no-store"
    assert client.get(f"{API}/conversations/unread-count").json() == {"unread_count": 2}

    read = client.post(
        f"{API}/conversations/{conversation_id}/read",
        params={"through": shown_cursor},
    )
    assert read.status_code == 204
    assert read.headers["cache-control"] == "no-store"
    assert client.get(f"{API}/conversations/unread-count").json() == {"unread_count": 1}


def test_cursors_pagination_boundaries_invalid_cursors_and_equal_timestamps(
    client, chat_env: ChatEnv
) -> None:
    """[TP-055] [FR-022]
    Перевіряє курсорну пагінацію розмов і повідомлень, взаємовиключність
    `after`/`before`, відхилення битих курсорів (422) та однакові timestamps.
    """
    buyer = chat_env.make_user(display_name="Покупець", email="b.cur@ukma.edu.ua")
    seller_a = chat_env.make_user(display_name="Продавець А", email="sa@ukma.edu.ua")
    seller_b = chat_env.make_user(display_name="Продавець Б", email="sb@ukma.edu.ua")
    seller_c = chat_env.make_user(display_name="Продавець В", email="sc@ukma.edu.ua")

    listing_a = chat_env.add_listing(seller_a, title="Лот А")
    listing_b = chat_env.add_listing(seller_b, title="Лот Б")
    listing_c = chat_env.add_listing(seller_c, title="Лот В")

    chat_env.authenticate(client, buyer)
    conv_a = client.post(
        f"{API}/listings/{listing_a.id}/conversation", json={"body": "А"}
    ).json()["conversation_id"]
    chat_env.advance(seconds=1)
    conv_b = client.post(
        f"{API}/listings/{listing_b.id}/conversation", json={"body": "Б"}
    ).json()["conversation_id"]
    chat_env.advance(seconds=1)
    conv_c = client.post(
        f"{API}/listings/{listing_c.id}/conversation", json={"body": "В"}
    ).json()["conversation_id"]

    # Пагінація списку розмов (limit=2 + cursor).
    p1 = client.get(f"{API}/conversations", params={"limit": 2}).json()
    assert [c["conversation_id"] for c in p1["items"]] == [conv_c, conv_b]
    assert p1["next_cursor"] is not None
    p2 = client.get(
        f"{API}/conversations", params={"limit": 2, "cursor": p1["next_cursor"]}
    ).json()
    assert [c["conversation_id"] for c in p2["items"]] == [conv_a]
    assert p2["next_cursor"] is None

    # Додаємо 4 повідомлення з ОДНАКОВИМ timestamp безпосередньо в репозиторій,
    # щоб перевірити стабільність порядку (created_at, message_id) і межу курсорів.
    same_ts = T0 + timedelta(seconds=10)
    equal_ids = [UUID(f"00000000-0000-4000-8000-00000000000{i}") for i in range(1, 5)]
    for idx, mid in enumerate(equal_ids, start=1):
        chat_env.conversations.add_message(
            Message(
                conversation_id=UUID(conv_a),
                sender_id=buyer.user_id,
                body=f"Однакова мітка #{idx}",
                created_at=same_ts,
                message_id=mid,
            )
        )

    # Разом у conv_a: 1 початкове ("А") + 4 з однаковим timestamp = 5 повідомлень.
    latest_page = client.get(
        f"{API}/conversations/{conv_a}/messages", params={"limit": 2}
    )
    assert latest_page.status_code == 200
    latest_data = latest_page.json()
    assert [m["body"] for m in latest_data["items"]] == [
        "Однакова мітка #3",
        "Однакова мітка #4",
    ]
    assert latest_data["has_more"] is True
    assert latest_data["before_cursor"] is not None

    older_page = client.get(
        f"{API}/conversations/{conv_a}/messages",
        params={"before": latest_data["before_cursor"], "limit": 2},
    ).json()
    assert [m["body"] for m in older_page["items"]] == [
        "Однакова мітка #1",
        "Однакова мітка #2",
    ]
    assert older_page["has_more"] is True

    oldest_page = client.get(
        f"{API}/conversations/{conv_a}/messages",
        params={"before": older_page["before_cursor"], "limit": 2},
    ).json()
    assert [m["body"] for m in oldest_page["items"]] == ["А"]
    assert oldest_page["has_more"] is False
    assert oldest_page["before_cursor"] is None

    # Forward-опитування з after через однакові timestamps: нічого не губиться.
    poll_first = client.get(
        f"{API}/conversations/{conv_a}/messages",
        params={"after": oldest_page["after_cursor"], "limit": 2},
    ).json()
    assert [m["body"] for m in poll_first["items"]] == [
        "Однакова мітка #1",
        "Однакова мітка #2",
    ]
    assert poll_first["has_more"] is True

    poll_second = client.get(
        f"{API}/conversations/{conv_a}/messages",
        params={"after": poll_first["after_cursor"], "limit": 2},
    ).json()
    assert [m["body"] for m in poll_second["items"]] == [
        "Однакова мітка #3",
        "Однакова мітка #4",
    ]
    assert poll_second["has_more"] is False

    # Разом after та before -> 422.
    both = client.get(
        f"{API}/conversations/{conv_a}/messages",
        params={
            "after": latest_data["after_cursor"],
            "before": latest_data["before_cursor"],
        },
    )
    assert both.status_code == 422
    assert both.headers.get("cache-control") == "no-store"

    # Невалідні / підроблені / порожні / задовгі курсори -> 422 (не 500).
    for bad_cursor in ("", "not-base64!", "a" * 200, "invalid|cursor"):
        bad_list = client.get(f"{API}/conversations", params={"cursor": bad_cursor})
        assert bad_list.status_code == 422
        assert bad_list.headers.get("cache-control") == "no-store"

        bad_after = client.get(
            f"{API}/conversations/{conv_a}/messages", params={"after": bad_cursor}
        )
        assert bad_after.status_code == 422
        assert bad_after.headers.get("cache-control") == "no-store"

        bad_before = client.get(
            f"{API}/conversations/{conv_a}/messages", params={"before": bad_cursor}
        )
        assert bad_before.status_code == 422
        assert bad_before.headers.get("cache-control") == "no-store"


# ---------------------------------------------------------------------------
# Валідація тексту, XSS, SQL-подібний ввід, безпека логів та 429 Retry-After
# ---------------------------------------------------------------------------


def test_text_validation_plain_string_xss_sql_and_log_safety(
    client, chat_env: ChatEnv, caplog
) -> None:
    """[TP-055] [FR-022] [SEC-003]
    Керівні та задовгі тексти дають 422 без витоку body чи cookie в логах;
    XSS, SQL-рядки та URL віддаються як звичайний текст без перетворення на HTML.
    """
    seller = chat_env.make_user(display_name="Продавець", email="s.txt@ukma.edu.ua")
    buyer = chat_env.make_user(display_name="Покупець", email="b.txt@ukma.edu.ua")
    listing = chat_env.add_listing(seller)
    token = chat_env.authenticate(client, buyer)

    secret_bad_body = "СЕКРЕТНЕ_НЕВАЛІДНЕ_ТІЛО\x00"
    with caplog.at_level(logging.INFO):
        res = client.post(
            f"{API}/listings/{listing.id}/conversation",
            json={"body": secret_bad_body},
        )
    assert res.status_code == 422
    assert res.headers.get("cache-control") == "no-store"
    _assert_no_secrets(res.text + caplog.text, (secret_bad_body, token))

    for invalid_body in ("hi\x07there", "rtl\u202espoof", "я" * 1001):
        r = client.post(
            f"{API}/listings/{listing.id}/conversation",
            json={"body": invalid_body},
        )
        assert r.status_code == 422
        assert r.headers.get("cache-control") == "no-store"

    # Валідне створення та перевірка XSS, URL і SQL-подібного вводу як тексту.
    xss_payload = "<script>alert(1)</script> https://naukma.edu.ua"
    sql_payload = "'; DROP TABLE messages; --"
    created = client.post(
        f"{API}/listings/{listing.id}/conversation",
        json={"body": xss_payload},
    )
    assert created.status_code == 201
    conv_id = created.json()["conversation_id"]
    assert created.json()["message"]["body"] == xss_payload
    assert "<a href" not in created.json()["message"]["body"]

    chat_env.advance(seconds=1)
    sql_res = client.post(
        f"{API}/conversations/{conv_id}/messages",
        json={"body": sql_payload},
    )
    assert sql_res.status_code == 201
    assert sql_res.json()["body"] == sql_payload

    messages = client.get(f"{API}/conversations/{conv_id}/messages").json()["items"]
    assert [m["body"] for m in messages] == [xss_payload, sql_payload]


def test_rate_limits_return_429_with_retry_after(client, chat_env: ChatEnv) -> None:
    """[TP-055] [FR-021] [FR-022]
    Перевищення ліміту повідомлень і нових розмов повертає 429 із Retry-After.
    """
    chat_env.settings[0] = ChatSettings(
        message_rate_per_minute=2,
        conversation_starts_per_day=1,
    )
    buyer = chat_env.make_user(display_name="Покупець", email="b.rate@ukma.edu.ua")
    seller_1 = chat_env.make_user(display_name="Продавець 1", email="s1@ukma.edu.ua")
    seller_2 = chat_env.make_user(display_name="Продавець 2", email="s2@ukma.edu.ua")
    listing_1 = chat_env.add_listing(seller_1, title="Товар 1")
    listing_2 = chat_env.add_listing(seller_2, title="Товар 2")

    chat_env.authenticate(client, buyer)
    first = client.post(
        f"{API}/listings/{listing_1.id}/conversation",
        json={"body": "Повідомлення 1"},
    )
    assert first.status_code == 201
    conv_id = first.json()["conversation_id"]

    # Ліміт нових розмов = 1/добу -> старт із іншим продавцем дає 429 + Retry-After.
    chat_env.advance(seconds=1)
    too_many_starts = client.post(
        f"{API}/listings/{listing_2.id}/conversation",
        json={"body": "Нова розмова"},
    )
    assert too_many_starts.status_code == 429
    assert too_many_starts.headers["retry-after"] == "86400"
    assert too_many_starts.headers.get("cache-control") == "no-store"

    # Друге повідомлення у наявну розмову дозволене (ліміт за хвилину = 2).
    chat_env.advance(seconds=1)
    second = client.post(
        f"{API}/conversations/{conv_id}/messages",
        json={"body": "Повідомлення 2"},
    )
    assert second.status_code == 201

    # Третє повідомлення в межах хвилини -> 429 з Retry-After=60.
    chat_env.advance(seconds=1)
    third = client.post(
        f"{API}/conversations/{conv_id}/messages",
        json={"body": "Повідомлення 3"},
    )
    assert third.status_code == 429
    assert third.headers["retry-after"] == "60"
    assert third.headers.get("cache-control") == "no-store"

    # Після завершення хвилинного вікна знову дозволено.
    chat_env.advance(seconds=61)
    recovered = client.post(
        f"{API}/conversations/{conv_id}/messages",
        json={"body": "Після паузи"},
    )
    assert recovered.status_code == 201


# ---------------------------------------------------------------------------
# Перевірка polling / PERF-002
# ---------------------------------------------------------------------------


def test_polling_every_5_seconds_delivers_within_10_seconds(
    client, chat_env: ChatEnv
) -> None:
    """[TP-056] [FR-022] [PERF-002] [SEC-003]
    Опитування відкритої розмови кожні 5 с доставляє нове повідомлення <= 10 с.
    """
    seller = chat_env.make_user(display_name="Продавець", email="s.poll@ukma.edu.ua")
    buyer = chat_env.make_user(display_name="Покупець", email="b.poll@ukma.edu.ua")
    listing = chat_env.add_listing(seller)

    # t=0s: покупець починає розмову й отримує початковий after_cursor.
    chat_env.authenticate(client, buyer)
    conv_id = client.post(
        f"{API}/listings/{listing.id}/conversation",
        json={"body": "Чи можна зустрітися о 16:00?"},
    ).json()["conversation_id"]
    initial = client.get(f"{API}/conversations/{conv_id}/messages").json()
    cursor = initial["after_cursor"]

    # t=2s: продавець відповідає.
    sent_at = chat_env.advance(seconds=2)
    chat_env.authenticate(client, seller)
    assert (
        client.post(
            f"{API}/conversations/{conv_id}/messages",
            json={"body": "Так, біля КМЦ"},
        ).status_code
        == 201
    )

    # t=5s (перший 5-секундний polling-цикл покупця від t=0): покупець бачить відповідь.
    polled_at = chat_env.advance(seconds=3)
    chat_env.authenticate(client, buyer)
    poll_res = client.get(
        f"{API}/conversations/{conv_id}/messages", params={"after": cursor}
    )
    assert poll_res.status_code == 200
    assert poll_res.headers["cache-control"] == "no-store"
    poll_data = poll_res.json()
    assert [m["body"] for m in poll_data["items"]] == ["Так, біля КМЦ"]
    assert (polled_at - sent_at).total_seconds() <= 10.0

    # t=10s (наступний polling з новим after_cursor): дублікатів немає.
    chat_env.advance(seconds=5)
    idle_poll = client.get(
        f"{API}/conversations/{conv_id}/messages",
        params={"after": poll_data["after_cursor"]},
    )
    assert idle_poll.status_code == 200
    assert idle_poll.json()["items"] == []
    assert idle_poll.json()["after_cursor"] == poll_data["after_cursor"]


def _as_actor(user: User) -> CurrentUser:
    return CurrentUser(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        entra_object_id=user.entra_object_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        avatar_url=user.avatar_url,
        contact=user.contact,
    )


def _chat_p95(durations: list[float]) -> float:
    """Return the nearest-rank p95 for one chat benchmark round."""
    if not durations:
        raise ValueError("chat p95 requires at least one duration")
    ordered = sorted(durations)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def _representative_chat_p95(round_p95s: list[float]) -> float:
    """Ignore one noisy round while preserving persistent regressions."""
    if not round_p95s:
        raise ValueError("representative chat p95 requires at least one round")
    return statistics.median(round_p95s)


def test_chat_benchmark_requires_most_rounds_to_meet_the_limit() -> None:
    """[TP-056] [PERF-002] Один шумний раунд не визначає результат benchmark."""
    assert _chat_p95([float(value) for value in range(1, 101)]) == 95.0
    assert _representative_chat_p95([0.140, 0.360, 0.160]) == pytest.approx(0.160)
    assert _representative_chat_p95([0.340, 0.150, 0.360]) == pytest.approx(0.340)


@pytest.mark.performance
@pytest.mark.anyio
async def test_nfr_perf_002_concurrent_chat_polling_50_users() -> None:
    """[TP-056] [PERF-002] [SEC-003]
    Бенчмарк polling чату: 50 одночасних користувачів опитують відкриті розмови;
    0% помилок, `Cache-Control: no-store`, без контактів,
    медіана round p95 <= 300 мс.
    """
    users = InMemoryUserRepository()
    listings = InMemoryListingRepository()
    conversations = InMemoryConversationRepository()
    sessions = InMemoryAuthSessionStore()
    activity = ActivityLogService(
        InMemoryActivityRepository(), users, InMemoryModerationActionRepository()
    )
    auth_service = AuthService(
        users,
        EntraAuthConfig(
            tenant_id=uuid4(),
            issuer="https://login.microsoftonline.com/test/v2.0",
            audience="baraholka-perf",
        ),
    )
    chat_service = ConversationService(conversations, listings, users, activity)

    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_user_repository] = lambda: users
    app.dependency_overrides[get_auth_session_store] = lambda: sessions
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_conversation_service] = lambda: chat_service

    try:
        sellers = []
        seller_listings = []
        for s_idx in range(5):
            seller = users.save(
                User(
                    user_id=uuid4(),
                    tenant_id=uuid4(),
                    entra_object_id=uuid4(),
                    email=f"perf.seller.{s_idx}@ukma.edu.ua",
                    display_name=f"Продавець {s_idx}",
                    contact=f"@perf_secret_contact_{s_idx}",
                )
            )
            listing = listings.save(
                Listing(
                    id=uuid4(),
                    title=f"Лот для тесту #{s_idx}",
                    description="",
                    price=100.0 + s_idx,
                    category_id=SEED_CATEGORY_ID,
                    contact=f"@perf_listing_secret_{s_idx}",
                    user_id=seller.user_id,
                    images=[ListingImage(image_url=SEED_IMAGE_URL, display_order=0)],
                )
            )
            sellers.append(_as_actor(seller))
            seller_listings.append(listing)

        clients_data: list[tuple[str, str, str]] = []
        for idx in range(50):
            seller_actor = sellers[idx % len(sellers)]
            listing = seller_listings[idx % len(seller_listings)]
            buyer = users.save(
                User(
                    user_id=uuid4(),
                    tenant_id=uuid4(),
                    entra_object_id=uuid4(),
                    email=f"perf.buyer.{idx}@ukma.edu.ua",
                    display_name=f"Покупець {idx}",
                    contact=f"@buyer_secret_{idx}",
                )
            )
            buyer_actor = _as_actor(buyer)
            start = chat_service.start_from_listing(
                buyer_actor, listing.id, f"Повідомлення {idx}"
            )
            page = chat_service.list_messages(buyer_actor, start.conversation_id)
            chat_service.send_message(
                seller_actor, start.conversation_id, f"Відповідь {idx}"
            )
            token = sessions.create(buyer.user_id)
            clients_data.append(
                (token, str(start.conversation_id), page.after_cursor or "")
            )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as async_client:
            # Кілька запитів прибирають cold-start із вимірювання.
            for _ in range(CHAT_WARMUP_REQUESTS):
                warmup = await async_client.get(
                    f"{API}/conversations/{clients_data[0][1]}/messages",
                    headers={"Cookie": f"{SESSION_COOKIE_NAME}={clients_data[0][0]}"},
                )
                assert warmup.status_code == 200

            async def poll_one(
                user_idx: int, token: str, conv_id: str, cursor: str
            ) -> dict:
                started = time.perf_counter()
                res = await async_client.get(
                    f"{API}/conversations/{conv_id}/messages",
                    params={"after": cursor},
                    headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"},
                )
                elapsed = time.perf_counter() - started
                return {
                    "idx": user_idx,
                    "status_code": res.status_code,
                    "cache_control": res.headers.get("cache-control"),
                    "text": res.text,
                    "items": res.json()["items"] if res.status_code == 200 else [],
                    "elapsed": elapsed,
                }

            round_p95s: list[float] = []
            round_means: list[float] = []
            round_maxima: list[float] = []
            for _ in range(CHAT_BENCHMARK_ROUNDS):
                results = await asyncio.gather(
                    *(
                        poll_one(i, tok, cid, cur)
                        for i, (tok, cid, cur) in enumerate(clients_data)
                    )
                )
                durations = [r["elapsed"] for r in results]
                round_p95s.append(_chat_p95(durations))
                round_means.append(statistics.mean(durations))
                round_maxima.append(max(durations))

                for r in results:
                    assert r["status_code"] == 200
                    assert r["cache_control"] == "no-store"
                    assert [m["body"] for m in r["items"]] == [f"Відповідь {r['idx']}"]
                    assert "@perf_secret_contact" not in r["text"]
                    assert "@perf_listing_secret" not in r["text"]

        representative_p95 = _representative_chat_p95(round_p95s)

        print(
            f"\n[PERF-002 Concurrent Chat Polling Benchmark]\n"
            f"Simultaneous Users: 50 | Rounds: {CHAT_BENCHMARK_ROUNDS} | "
            f"Round p95: {[round(value * 1000, 2) for value in round_p95s]} ms | "
            f"Median p95: {representative_p95 * 1000:.2f} ms | "
            f"Mean range: {min(round_means) * 1000:.2f}–"
            f"{max(round_means) * 1000:.2f} ms | "
            f"Max: {max(round_maxima) * 1000:.2f} ms | Errors: 0.0%"
        )
        assert representative_p95 <= 0.300, (
            "Порушення PERF-002: медіана p95 = "
            f"{representative_p95 * 1000:.2f} мс > 300 мс; "
            f"раунди = {[round(value * 1000, 2) for value in round_p95s]} мс"
        )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved_overrides)


def test_reply_to_message_returns_quote_and_rejects_foreign_id(
    client, chat_env: ChatEnv
) -> None:
    """[TP-055] [FR-022] [SEC-003]
    Відповідь повертає цитату; id повідомлення з іншої розмови чи вигаданий дають 422.
    """
    seller = chat_env.make_user(display_name="Продавець", email="s.reply@ukma.edu.ua")
    buyer = chat_env.make_user(display_name="Покупець", email="b.reply@ukma.edu.ua")
    other = chat_env.make_user(display_name="Інший", email="o.reply@ukma.edu.ua")
    listing = chat_env.add_listing(seller, title="Лампа", price=100.0)
    other_listing = chat_env.add_listing(seller, title="Стілець", price=50.0)

    chat_env.authenticate(client, other)
    foreign = client.post(
        f"{API}/listings/{other_listing.id}/conversation", json={"body": "Чужа"}
    ).json()["message"]["message_id"]

    chat_env.authenticate(client, buyer)
    started = client.post(
        f"{API}/listings/{listing.id}/conversation", json={"body": "Привіт"}
    ).json()
    conversation_id = started["conversation_id"]
    first_id = started["message"]["message_id"]

    chat_env.authenticate(client, seller)
    reply = client.post(
        f"{API}/conversations/{conversation_id}/messages",
        json={"body": "Добрий день", "reply_to_id": first_id},
    )
    assert reply.status_code == 201
    quote = reply.json()["reply_to"]
    assert quote["message_id"] == first_id
    assert quote["body"] == "Привіт"
    assert quote["is_own"] is False

    for bad_id in (foreign, str(uuid4())):
        bad = client.post(
            f"{API}/conversations/{conversation_id}/messages",
            json={"body": "Ні", "reply_to_id": bad_id},
        )
        assert bad.status_code == 422
        assert bad.headers.get("cache-control") == "no-store"


@pytest.fixture
def report_env(chat_env: ChatEnv, monkeypatch):
    """Підключає сервіс скарг на повідомлення до сховища розмов `chat_env`."""
    from src.api.deps import get_message_report_service
    from src.repositories.message_reports import InMemoryMessageReportRepository
    from src.services.message_reports import MessageReportService

    reports = InMemoryMessageReportRepository()
    monkeypatch.setitem(
        app.dependency_overrides,
        get_message_report_service,
        lambda: MessageReportService(reports, chat_env.conversations, chat_env.users),
    )
    return chat_env


def test_message_report_flow_snapshot_duplicates_and_admin_resolution(
    client, report_env: ChatEnv
) -> None:
    """[TP-055] [FR-022] [SEC-003]
    Учасник скаржиться на чуже повідомлення; дублікат 409, власне чи чуже
    повідомлення 422/404; адміністратор бачить знімок і розглядає скаргу.
    """
    seller = report_env.make_user(display_name="Продавець", email="s.rep@ukma.edu.ua")
    buyer = report_env.make_user(display_name="Покупець", email="b.rep@ukma.edu.ua")
    stranger = report_env.make_user(display_name="Сторонній", email="x.rep@ukma.edu.ua")
    admin = report_env.make_user(
        display_name="Адмін", email="a.rep@ukma.edu.ua", role=UserRole.ADMIN
    )
    listing = report_env.add_listing(seller, title="Лампа", price=100.0)

    report_env.authenticate(client, buyer)
    started = client.post(
        f"{API}/listings/{listing.id}/conversation", json={"body": "Купи в мене крипту"}
    ).json()
    conversation_id = started["conversation_id"]
    own_id = started["message"]["message_id"]

    report_env.authenticate(client, seller)
    path = f"{API}/conversations/{conversation_id}/messages/{own_id}/report"
    assert client.post(path, json={"reason": "OTHER"}).status_code == 422
    first = client.post(path, json={"reason": "SPAM", "details": "реклама"})
    assert first.status_code == 204
    assert first.headers.get("cache-control") == "no-store"
    assert client.post(path, json={"reason": "SPAM"}).status_code == 409

    # Власне повідомлення: 422; сторонній і вигадане повідомлення: однакова 404.
    reply = client.post(
        f"{API}/conversations/{conversation_id}/messages", json={"body": "Ні"}
    ).json()
    own_path = f"{API}/conversations/{conversation_id}/messages/{reply['message_id']}"
    assert client.post(own_path + "/report", json={"reason": "SPAM"}).status_code == 422
    report_env.authenticate(client, stranger)
    foreign = client.post(path, json={"reason": "SPAM"})
    missing = client.post(
        f"{API}/conversations/{conversation_id}/messages/{uuid4()}/report",
        json={"reason": "SPAM"},
    )
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()

    # Звичайний користувач не бачить адмінського списку.
    assert client.get(f"{API}/admin/message-reports").status_code == 403

    report_env.authenticate(client, admin)
    listed = client.get(f"{API}/admin/message-reports")
    assert listed.status_code == 200
    item = listed.json()[0]
    assert item["body_snapshot"] == "Купи в мене крипту"
    assert item["reporter_name"] == "Продавець"
    assert item["reported_name"] == "Покупець"
    assert item["status"] == "OPEN"

    resolve = client.post(
        f"{API}/admin/message-reports/{item['id']}/resolve",
        json={"status": "RESOLVED", "note": "попередження"},
    )
    assert resolve.status_code == 200
    assert resolve.json()["status"] == "RESOLVED"
    again = client.post(
        f"{API}/admin/message-reports/{item['id']}/resolve",
        json={"status": "DISMISSED"},
    )
    assert again.status_code == 409
    assert client.get(f"{API}/admin/message-reports?status=OPEN").json() == []


def test_messages_expose_peer_read_marker_for_read_receipts(
    client, chat_env: ChatEnv
) -> None:
    """[TP-055] Відправник бачить, до якого повідомлення прочитав співрозмовник."""
    seller = chat_env.make_user(
        display_name="Продавець",
        email="seller.receipt@ukma.edu.ua",
    )
    buyer = chat_env.make_user(
        display_name="Покупець",
        email="buyer.receipt@ukma.edu.ua",
    )
    listing = chat_env.add_listing(seller)

    chat_env.authenticate(client, buyer)
    started = client.post(
        f"{API}/listings/{listing.id}/conversation", json={"body": "Привіт"}
    )
    conversation_id = started.json()["conversation_id"]
    url = f"{API}/conversations/{conversation_id}/messages"
    first = client.get(url).json()
    assert first["peer_read"] is None

    chat_env.authenticate(client, seller)
    assert client.post(f"{API}/conversations/{conversation_id}/read").status_code == 204

    chat_env.authenticate(client, buyer)
    after = client.get(url).json()
    assert after["peer_read"]["message_id"] == after["items"][-1]["message_id"]
    assert set(after["peer_read"]) == {"created_at", "message_id"}
