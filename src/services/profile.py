"""Редагування профілю: ім'я, контакти, аватарка (FR-014, US-009)."""

from uuid import UUID

from src.domain.exceptions import (
    InvalidListingImageError,
    InvalidProfileError,
    ProfileNotFoundError,
)
from src.domain.users import CurrentUser, User
from src.repositories.image_storage import ImageStorage, normalize_storage_key
from src.repositories.users import UserRepository

MAX_DISPLAY_NAME_LENGTH = 100
MAX_CONTACT_LENGTH = 300


class ProfileService:
    """Змінює лише власний профіль; аватарка зберігається як зображення з
    псевдо-ідентифікатором `user_id`, тому не підпадає під TTL staged-завантажень."""

    def __init__(self, users: UserRepository, images: ImageStorage) -> None:
        self._users = users
        self._images = images

    def _get(self, user_id: UUID) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise ProfileNotFoundError("Профіль користувача не знайдено")
        return user

    @staticmethod
    def _to_current(user: User, base: CurrentUser) -> CurrentUser:
        return CurrentUser(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            entra_object_id=user.entra_object_id,
            email=user.email,
            display_name=user.display_name,
            role=base.role,
            avatar_url=user.avatar_url,
            contact=user.contact,
        )

    def get_public(self, user_id: UUID) -> User:
        return self._get(user_id)

    def update(
        self,
        actor: CurrentUser,
        *,
        display_name: str | None = None,
        update_name: bool = False,
        contact: str | None = None,
        update_contact: bool = False,
    ) -> CurrentUser:
        user = self._get(actor.user_id)
        if update_name:
            name = (display_name or "").strip()
            if not name or len(name) > MAX_DISPLAY_NAME_LENGTH:
                raise InvalidProfileError(
                    f"Ім'я має містити від 1 до {MAX_DISPLAY_NAME_LENGTH} символів"
                )
            user.display_name = name
            user.display_name_customized = True
        if update_contact:
            value = (contact or "").strip()
            if len(value) > MAX_CONTACT_LENGTH:
                raise InvalidProfileError(
                    f"Контакти не можуть перевищувати {MAX_CONTACT_LENGTH} символів"
                )
            user.contact = value or None
        return self._to_current(self._users.save(user), actor)

    def set_avatar(self, actor: CurrentUser, data: bytes) -> CurrentUser:
        user = self._get(actor.user_id)
        try:
            saved = self._images.save_images(
                user.user_id, [data], actor_id=user.user_id
            )
        except InvalidListingImageError as exc:
            raise InvalidProfileError(str(exc)) from exc
        user.avatar_url = saved[0].image_url
        return self._to_current(self._users.save(user), actor)

    def remove_avatar(self, actor: CurrentUser) -> CurrentUser:
        user = self._get(actor.user_id)
        if user.avatar_url:
            try:
                self._images.delete_images([normalize_storage_key(user.avatar_url)])
            except InvalidListingImageError:
                pass
            user.avatar_url = None
            user = self._users.save(user)
        return self._to_current(user, actor)
