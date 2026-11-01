"""Create or remove clearly marked test listings in PostgreSQL.

Run inside the production-like API container, where ``DATABASE_URL`` and
``IMAGE_STORAGE_DIR`` already point at the configured database and uploads
volume::

    docker compose exec api python -m scripts.seed_listings \
        --owner-email student@ukma.edu.ua --count 20

    docker compose exec api python -m scripts.seed_listings \
        --owner-email student@ukma.edu.ua --cleanup --yes

The owner must already exist (sign in once before seeding).  Cleanup removes
only listings whose titles start with ``[SEED]`` and belong to that owner.
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import sys

from PIL import Image, ImageDraw

from src.config import get_image_storage_dir
from src.db.engine import get_session_factory
from src.domain.listings import ListingCondition
from src.repositories.image_storage import LocalImageStorage
from src.repositories.postgres_categories import PostgresCategoryRepository
from src.repositories.postgres_listings import PostgresListingRepository
from src.repositories.postgres_users import PostgresUserRepository
from src.services.listings import ListingService

SEED_TITLE_PREFIX = "[SEED]"
MAX_BATCH_SIZE = 10
MAX_SEED_COUNT = 500


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or remove test listings in the configured PostgreSQL DB."
    )
    parser.add_argument(
        "--owner-email",
        required=True,
        help="Email of an existing user who will own the test listings.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=20,
        help=f"Number of listings to create (1..{MAX_SEED_COUNT}, default: 20).",
    )
    parser.add_argument(
        "--category-slug",
        help="Active category slug; defaults to the first active category.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove this owner's listings whose titles start with [SEED].",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm the destructive --cleanup operation.",
    )
    args = parser.parse_args()
    if not 1 <= args.count <= MAX_SEED_COUNT:
        parser.error(f"--count must be between 1 and {MAX_SEED_COUNT}")
    if args.cleanup and not args.yes:
        parser.error("--cleanup requires --yes")
    return args


def make_test_image(index: int) -> bytes:
    """Return a small valid JPEG with a deterministic color and label."""
    color = ((index * 47) % 190 + 40, (index * 83) % 190 + 40, 120)
    image = Image.new("RGB", (900, 600), color)
    draw = ImageDraw.Draw(image)
    draw.text((50, 275), f"Baraholka seed #{index:03d}", fill=(15, 15, 15))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def select_category(repository, slug: str | None):
    if slug:
        category = repository.get_by_slug(slug)
        if category is None or not category.is_active:
            raise RuntimeError(f"Active category with slug '{slug}' was not found")
        return category
    categories = repository.list_active()
    if not categories:
        raise RuntimeError("No active categories found; create a category first")
    return categories[0]


def cleanup_seed_listings(session, owner, storage: LocalImageStorage) -> int:
    repository = PostgresListingRepository(session)
    targets = [
        listing
        for listing in repository.list_by_owner(owner.user_id)
        if listing.title.startswith(SEED_TITLE_PREFIX)
    ]
    image_keys = [
        image.storage_key
        for listing in targets
        for image in listing.images
        if image.storage_key
    ]
    for listing in targets:
        repository.delete(listing.id)
    session.commit()
    if image_keys:
        storage.delete_images(image_keys)
    return len(targets)


def create_seed_listings(
    session,
    owner,
    storage: LocalImageStorage,
    *,
    count: int,
    category_slug: str | None,
) -> int:
    listing_repository = PostgresListingRepository(session)
    category_repository = PostgresCategoryRepository(session)
    category = select_category(category_repository, category_slug)
    service = ListingService(
        listing_repository,
        image_storage=storage,
        category_validator=lambda category_id: (
            (item := category_repository.get(category_id)) is not None
            and item.is_active
        ),
    )

    created = 0
    for offset in range(0, count, MAX_BATCH_SIZE):
        batch_size = min(MAX_BATCH_SIZE, count - offset)
        images = storage.upload_images(
            [make_test_image(offset + index + 1) for index in range(batch_size)],
            actor_id=owner.user_id,
        )
        keys = [image.storage_key for image in images if image.storage_key]
        if len(keys) != batch_size:
            storage.delete_images(keys)
            raise RuntimeError("Image storage did not return all expected keys")

        for index, key in enumerate(keys, start=offset + 1):
            try:
                service.create(
                    actor_id=owner.user_id,
                    title=f"{SEED_TITLE_PREFIX} Тестове оголошення {index:03d}",
                    description=(
                        "Автоматично створене тестове оголошення. "
                        "Його можна безпечно видалити seed-скриптом."
                    ),
                    price=float(100 + index * 25),
                    category_id=category.id,
                    contact=owner.contact or owner.email,
                    condition=ListingCondition.GOOD,
                    image_urls=[key],
                )
                session.commit()
                created += 1
                print(f"Created {created}/{count}")
            except Exception:
                session.rollback()
                storage.delete_images([key])
                storage.delete_images(keys[index - offset :])
                raise
    return created


def main() -> int:
    args = parse_args()
    storage_dir: Path = get_image_storage_dir()
    # This is an explicit maintenance command, so its own in-process storage
    # adapter may seed more batches than the public upload endpoint permits.
    storage = LocalImageStorage(
        storage_dir,
        max_requests_per_window=MAX_SEED_COUNT,
    )
    session = get_session_factory()()
    try:
        owner = PostgresUserRepository(session).get_by_email(args.owner_email)
        if owner is None:
            raise RuntimeError(
                f"User '{args.owner_email}' was not found. Sign in once before seeding."
            )
        if args.cleanup:
            removed = cleanup_seed_listings(session, owner, storage)
            print(f"Removed {removed} seed listings")
        else:
            created = create_seed_listings(
                session,
                owner,
                storage,
                count=args.count,
                category_slug=args.category_slug,
            )
            print(f"Done: created {created} seed listings")
        return 0
    except Exception as exc:
        session.rollback()
        print(f"Seed operation failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
