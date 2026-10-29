"""Модуль завантаження, нормалізації та зберігання зображень (FR-002, TM-03, TM-08)."""

from collections.abc import Sequence
from dataclasses import dataclass
import io
from pathlib import Path
import re
from typing import Protocol
from uuid import UUID, uuid4
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
import pillow_heif

from src.domain.exceptions import InvalidListingImageError
from src.domain.listings import (
    SEED_IMAGE_ID,
    SEED_IMAGE_STORAGE_KEY,
    SEED_LISTING_ID,
    ListingImage,
)

# Реєструємо HEIF/HEIC декодер для Pillow
pillow_heif.register_heif_opener()

MIN_IMAGES_PER_LISTING = 1
MAX_IMAGES_PER_LISTING = 10
MAX_IMAGE_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 МБ
MAX_IMAGE_PIXELS = 25_000_000  # 25 MP (захист від decompression bomb)
MAX_MAIN_DIMENSION = 1600
MAX_THUMBNAIL_DIMENSION = 400
WEBP_QUALITY = 80
PUBLIC_UPLOADS_PREFIX = "/uploads/"

ALLOWED_PILLOW_FORMATS = frozenset({"JPEG", "PNG", "WEBP", "HEIF", "HEIC"})
ALLOWED_ISOBMFF_BRANDS = frozenset(
    {
        b"heic",
        b"heix",
        b"hevc",
        b"hevx",
        b"heim",
        b"heis",
        b"hevm",
        b"hevs",
        b"mif1",
        b"heif",
    }
)

STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}(?:_thumb)?\.webp$")
MAIN_STORAGE_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.webp$")


@dataclass(frozen=True)
class ProcessedImage:
    """Нормалізовані версії зображення: основне та thumbnail у форматі WebP."""

    main_bytes: bytes
    thumbnail_bytes: bytes
    width: int
    height: int
    thumbnail_width: int
    thumbnail_height: int
    source_format: str


def normalize_storage_key(reference: str) -> str:
    """Валідує посилання/ключ зображення та виділяє чистий storage key (32-hex.webp).

    Забороняє зовнішні URL, path traversal та сторонні назви файлів.
    """
    cleaned = reference.strip()
    if not cleaned:
        raise InvalidListingImageError("Ключ зображення не може бути порожнім")

    # Відхиляємо зовнішні URL-схеми
    if "://" in cleaned or cleaned.startswith(
        ("http:", "https:", "ftp:", "file:", "data:")
    ):
        raise InvalidListingImageError(
            "Зовнішні URL заборонені; використовуйте завантажені файли"
        )

    # Захист від path traversal та заборонених символів
    if ".." in cleaned or "\\" in cleaned or " " in cleaned:
        raise InvalidListingImageError("Некоректний ключ або шлях зображення")

    if cleaned.startswith(PUBLIC_UPLOADS_PREFIX):
        key = cleaned[len(PUBLIC_UPLOADS_PREFIX) :]
    else:
        key = cleaned

    if not MAIN_STORAGE_KEY_PATTERN.fullmatch(key):
        raise InvalidListingImageError(
            "Ключ зображення має відповідати згенерованому серверному WebP-файлу"
        )
    return key


def thumbnail_key_for(storage_key: str) -> str:
    """Генерує ключ thumbnail-файла для заданого основного storage key."""
    if storage_key.endswith("_thumb.webp"):
        return storage_key
    if storage_key.endswith(".webp"):
        return storage_key[:-5] + "_thumb.webp"
    return f"{storage_key}_thumb.webp"


def _check_raw_file_header(raw_bytes: bytes) -> None:
    """Перевіряє бінарні сигнатури на рівні заголовка файла до запуску декодера."""
    header_snippet = raw_bytes[:512].lower()

    # Відхилення SVG / XML
    if (
        b"<svg" in header_snippet
        or b"<?xml" in header_snippet
        or b"<!doctype svg" in header_snippet
    ):
        raise InvalidListingImageError("Формат SVG заборонено з міркувань безпеки")

    # Відхилення RAW/DNG/TIFF
    if raw_bytes.startswith((b"II*\x00", b"MM\x00*")):
        raise InvalidListingImageError("RAW/DNG та TIFF формати не підтримуються")

    # Перевірка контейнера ISO-BMFF (HEIC, HEIF, MOV, MP4)
    if len(raw_bytes) >= 12 and raw_bytes[4:8] == b"ftyp":
        major_brand = raw_bytes[8:12]
        if major_brand in {b"qt  ", b"isom", b"mp41", b"mp42", b"m4v "}:
            raise InvalidListingImageError(
                "Відеофайли та Live Photo (.mov/.mp4) не підтримуються"
            )
        if major_brand not in ALLOWED_ISOBMFF_BRANDS:
            brand_str = major_brand.decode("latin1", errors="replace")
            raise InvalidListingImageError(
                f"Непідтримуваний контейнер медіафайлу ({brand_str})"
            )


def process_image_bytes(
    raw_bytes: bytes,
    *,
    max_file_size: int = MAX_IMAGE_FILE_SIZE_BYTES,
    max_pixels: int = MAX_IMAGE_PIXELS,
) -> ProcessedImage:
    """Декодує, перевіряє, нормалізує розміри й формат і видаляє метадані.

    - Дозволені формати: JPEG, PNG, WebP, HEIC, HEIF.
    - Перевірка фактичного декодування байтів.
    - Захист від decompression bomb (обмеження пікселів).
    - Заборона SVG, анімованих та невідомих форматів.
    - EXIF-orientation нормалізація.
    - Повне видалення EXIF, XMP, GPS, ICC.
    - Основне зображення: довша сторона <= 1600 px (без апскейлу).
    - Thumbnail: довша сторона <= 400 px (без апскейлу).
    - Вихідний формат: WebP (quality=80).
    """
    if not isinstance(raw_bytes, (bytes, bytearray)) or len(raw_bytes) == 0:
        raise InvalidListingImageError("Файл зображення порожній")

    if len(raw_bytes) > max_file_size:
        max_mb = max_file_size // (1024 * 1024)
        raise InvalidListingImageError(
            f"Розмір файла перевищує максимально допустимі {max_mb} МБ"
        )

    _check_raw_file_header(raw_bytes)

    # Декодування Pillow з контролем DecompressionBomb
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            prev_max = Image.MAX_IMAGE_PIXELS
            Image.MAX_IMAGE_PIXELS = max_pixels
            try:
                img = Image.open(io.BytesIO(raw_bytes))
                fmt = (img.format or "").upper()
                if fmt not in ALLOWED_PILLOW_FORMATS:
                    raise InvalidListingImageError(
                        f"Формат зображення {fmt or 'UNKNOWN'} не підтримується"
                    )

                w, h = img.size
                if w <= 0 or h <= 0 or (w * h) > max_pixels:
                    raise InvalidListingImageError(
                        "Зображення перевищує допустиму кількість "
                        "пікселів (decompression bomb)"
                    )

                # Перевірка на анімовані формати (APNG, Animated WebP, GIF)
                if (
                    getattr(img, "is_animated", False)
                    or getattr(img, "n_frames", 1) > 1
                ):
                    raise InvalidListingImageError(
                        "Анімовані зображення або серії кадрів не підтримуються"
                    )

                # Фактичне декодування пікселів
                img.load()
            finally:
                Image.MAX_IMAGE_PIXELS = prev_max

    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidListingImageError(
            "Зображення перевищує допустиму кількість пікселів (decompression bomb)"
        ) from exc
    except UnidentifiedImageError as exc:
        raise InvalidListingImageError(
            "Неможливо розпізнати або декодувати файл зображення"
        ) from exc
    except (OSError, ValueError, SyntaxError) as exc:
        raise InvalidListingImageError(
            f"Помилка декодування файлу зображення: {exc}"
        ) from exc

    # Застосування EXIF-орієнтації
    try:
        oriented = ImageOps.exif_transpose(img)
        if oriented is None:
            oriented = img
    except Exception:
        oriented = img

    if (oriented.width * oriented.height) > max_pixels:
        raise InvalidListingImageError(
            "Зображення перевищує допустиму кількість пікселів після трансформації"
        )

    # Нормалізація колірного режиму (для прозорості — RGBA, для решти — RGB)
    if oriented.mode in ("RGBA", "LA") or (
        oriented.mode == "P" and "transparency" in oriented.info
    ):
        rgb_img = oriented.convert("RGBA")
    else:
        rgb_img = oriented.convert("RGB")

    # Створення повністю чистого об'єкта зображення без EXIF/XMP/GPS метаданих
    clean = Image.frombytes(rgb_img.mode, rgb_img.size, rgb_img.tobytes())

    # Масштабування основного зображення (довша сторона <= 1600 px, без апскейлу)
    orig_w, orig_h = clean.size
    if max(orig_w, orig_h) > MAX_MAIN_DIMENSION:
        main_img = ImageOps.contain(
            clean,
            (MAX_MAIN_DIMENSION, MAX_MAIN_DIMENSION),
            method=Image.Resampling.LANCZOS,
        )
    else:
        main_img = clean.copy()

    # Масштабування thumbnail (довша сторона <= 400 px, без апскейлу)
    if max(orig_w, orig_h) > MAX_THUMBNAIL_DIMENSION:
        thumb_img = ImageOps.contain(
            clean,
            (MAX_THUMBNAIL_DIMENSION, MAX_THUMBNAIL_DIMENSION),
            method=Image.Resampling.LANCZOS,
        )
    else:
        thumb_img = clean.copy()

    # Збереження у WebP quality=80
    main_buf = io.BytesIO()
    main_img.save(main_buf, format="WEBP", quality=WEBP_QUALITY)
    main_bytes = main_buf.getvalue()

    thumb_buf = io.BytesIO()
    thumb_img.save(thumb_buf, format="WEBP", quality=WEBP_QUALITY)
    thumb_bytes = thumb_buf.getvalue()

    return ProcessedImage(
        main_bytes=main_bytes,
        thumbnail_bytes=thumb_bytes,
        width=main_img.width,
        height=main_img.height,
        thumbnail_width=thumb_img.width,
        thumbnail_height=thumb_img.height,
        source_format=fmt,
    )


def create_listing_image(
    *,
    image_id: UUID,
    storage_key: str,
    listing_id: UUID | None = None,
    display_order: int = 0,
    width: int | None = None,
    height: int | None = None,
    thumbnail_width: int | None = None,
    thumbnail_height: int | None = None,
) -> ListingImage:
    """Створює екземпляр ListingImage з канонічними URL."""
    thumb_key = thumbnail_key_for(storage_key)
    return ListingImage(
        image_id=image_id,
        listing_id=listing_id,
        image_url=f"{PUBLIC_UPLOADS_PREFIX}{storage_key}",
        thumbnail_url=f"{PUBLIC_UPLOADS_PREFIX}{thumb_key}",
        storage_key=storage_key,
        display_order=display_order,
        width=width,
        height=height,
        thumbnail_width=thumbnail_width,
        thumbnail_height=thumbnail_height,
    )


def create_listing_image_from_proc(
    *,
    image_id: UUID,
    storage_key: str,
    proc: ProcessedImage,
    listing_id: UUID | None = None,
    display_order: int = 0,
) -> ListingImage:
    """Створює ListingImage на основі ProcessedImage."""
    return create_listing_image(
        image_id=image_id,
        storage_key=storage_key,
        listing_id=listing_id,
        display_order=display_order,
        width=proc.width,
        height=proc.height,
        thumbnail_width=proc.thumbnail_width,
        thumbnail_height=proc.thumbnail_height,
    )


def validate_images_count(
    items: Sequence[object],
    *,
    min_msg: str,
    max_msg: str,
) -> None:
    """Перевіряє кількість елементів у діапазоні MIN..MAX."""
    if len(items) < MIN_IMAGES_PER_LISTING:
        raise InvalidListingImageError(min_msg)
    if len(items) > MAX_IMAGES_PER_LISTING:
        raise InvalidListingImageError(max_msg)


class BaseImageStorage:
    """Спільний базовий клас асоціацій зображень та оголошень."""

    def __init__(self) -> None:
        self._listing_images: dict[UUID, list[ListingImage]] = {}
        self._key_to_listing: dict[str, UUID] = {}

    def get_images(self, listing_id: UUID) -> list[ListingImage]:
        return list(self._listing_images.get(listing_id, []))

    def _verify_unbound_or_owned(self, key: str, listing_id: UUID) -> None:
        bound_to = self._key_to_listing.get(key)
        if (
            bound_to is not None
            and bound_to != listing_id
            and key != SEED_IMAGE_STORAGE_KEY
        ):
            raise InvalidListingImageError(
                f"Зображення {key} вже прив'язано до іншого оголошення"
            )

    def _commit_listing_update(
        self, listing_id: UUID, resolved_items: list[ListingImage]
    ) -> list[ListingImage]:
        previous_images = self._listing_images.get(listing_id, [])
        old_keys = {img.storage_key for img in previous_images if img.storage_key}
        new_keys = {img.storage_key for img in resolved_items if img.storage_key}
        keys_to_delete = old_keys - new_keys

        if keys_to_delete:
            self.delete_images(list(keys_to_delete))

        for key in new_keys:
            self._key_to_listing[key] = listing_id

        self._listing_images[listing_id] = list(resolved_items)
        return list(resolved_items)


class ImageStorage(Protocol):
    """Контракт збереження та отримання фотографій оголошення (FR-002, TM-03)."""

    def upload_images(self, files: Sequence[bytes]) -> list[ListingImage]:
        """Обробляє, нормалізує та зберігає пачку файлів (FR-002)."""

    def save_images(
        self, listing_id: UUID, images: Sequence[bytes | str]
    ) -> list[ListingImage]:
        """Валідує та прив'язує зображення до оголошення (FR-002)."""

    def get_images(self, listing_id: UUID) -> list[ListingImage]:
        """Повертає збережені зображення оголошення у порядку display_order."""

    def delete_images(self, storage_keys: Sequence[str]) -> None:
        """Видаляє вказані зображення (основні та thumbnail)."""

    def read_image(self, storage_key: str) -> bytes:
        """Читає бінарні дані зображення за його storage key."""


class InMemoryImageStorage(BaseImageStorage):
    """In-memory реалізація ImageStorage для тестів."""

    def __init__(self) -> None:
        super().__init__()
        self._blobs: dict[str, bytes] = {}
        self._staged_images: dict[str, ListingImage] = {}
        self._init_seed_image()

    def _init_seed_image(self) -> None:
        dummy_webp = (
            b"RIFF\x14\x00\x00\x00WEBPVP8 "
            b"\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        )
        self._blobs[SEED_IMAGE_STORAGE_KEY] = dummy_webp
        thumb_key = thumbnail_key_for(SEED_IMAGE_STORAGE_KEY)
        self._blobs[thumb_key] = dummy_webp
        seed_item = create_listing_image(
            image_id=SEED_IMAGE_ID,
            storage_key=SEED_IMAGE_STORAGE_KEY,
            listing_id=SEED_LISTING_ID,
            display_order=0,
            width=800,
            height=600,
            thumbnail_width=400,
            thumbnail_height=300,
        )
        self._staged_images[SEED_IMAGE_STORAGE_KEY] = seed_item
        self._listing_images[SEED_LISTING_ID] = [seed_item]
        self._key_to_listing[SEED_IMAGE_STORAGE_KEY] = SEED_LISTING_ID

    def upload_images(self, files: Sequence[bytes]) -> list[ListingImage]:
        validate_images_count(
            files,
            min_msg="Потрібно завантажити щонайменше одне фото (FR-002)",
            max_msg=(
                f"Кількість завантажуваних фото не може "
                f"перевищувати {MAX_IMAGES_PER_LISTING}"
            ),
        )

        ready_batch = [(uuid4(), process_image_bytes(data)) for data in files]

        results: list[ListingImage] = []
        for index, (image_id, proc) in enumerate(ready_batch):
            main_key = f"{image_id.hex}.webp"
            thumb_key = f"{image_id.hex}_thumb.webp"
            self._blobs[main_key] = proc.main_bytes
            self._blobs[thumb_key] = proc.thumbnail_bytes
            item = create_listing_image_from_proc(
                image_id=image_id,
                storage_key=main_key,
                proc=proc,
                display_order=index,
            )
            self._staged_images[main_key] = item
            results.append(item)
        return results

    def save_images(
        self, listing_id: UUID, images: Sequence[bytes | str]
    ) -> list[ListingImage]:
        validate_images_count(
            images,
            min_msg="Оголошення має містити щонайменше одне зображення (FR-002)",
            max_msg=(
                f"Кількість зображень не може " f"перевищувати {MAX_IMAGES_PER_LISTING}"
            ),
        )

        seen_keys: set[str] = set()
        resolved_items: list[ListingImage] = []
        new_blobs_to_add: dict[str, bytes] = {}
        new_items_to_stage: list[tuple[str, ListingImage]] = []

        for index, item in enumerate(images):
            if isinstance(item, (bytes, bytearray)):
                proc = process_image_bytes(item)
                image_id = uuid4()
                main_key = f"{image_id.hex}.webp"
                thumb_key = f"{image_id.hex}_thumb.webp"
                new_blobs_to_add[main_key] = proc.main_bytes
                new_blobs_to_add[thumb_key] = proc.thumbnail_bytes
                staged = create_listing_image_from_proc(
                    image_id=image_id,
                    storage_key=main_key,
                    proc=proc,
                    listing_id=listing_id,
                    display_order=index,
                )
                new_items_to_stage.append((main_key, staged))
                resolved_items.append(staged)
                seen_keys.add(main_key)
            elif isinstance(item, str):
                key = normalize_storage_key(item)
                if key in seen_keys:
                    raise InvalidListingImageError(
                        f"Дубльоване зображення {key} в одному оголошенні"
                    )
                seen_keys.add(key)

                if key not in self._blobs:
                    raise InvalidListingImageError(
                        f"Зображення {key} не знайдено у сховищі"
                    )

                self._verify_unbound_or_owned(key, listing_id)

                existing_meta = self._staged_images.get(key)
                img_id = (
                    existing_meta.image_id if existing_meta else UUID(key.split(".")[0])
                )
                resolved_items.append(
                    create_listing_image(
                        image_id=img_id,
                        storage_key=key,
                        listing_id=listing_id,
                        display_order=index,
                        width=existing_meta.width if existing_meta else None,
                        height=existing_meta.height if existing_meta else None,
                        thumbnail_width=(
                            existing_meta.thumbnail_width if existing_meta else None
                        ),
                        thumbnail_height=(
                            existing_meta.thumbnail_height if existing_meta else None
                        ),
                    )
                )
            else:
                raise InvalidListingImageError("Непідтримуваний тип даних зображення")

        for k, v in new_blobs_to_add.items():
            self._blobs[k] = v
        for k, staged_item in new_items_to_stage:
            self._staged_images[k] = staged_item

        return self._commit_listing_update(listing_id, resolved_items)

    def delete_images(self, storage_keys: Sequence[str]) -> None:
        for raw_key in storage_keys:
            key = (
                normalize_storage_key(raw_key)
                if not STORAGE_KEY_PATTERN.fullmatch(raw_key)
                else raw_key
            )
            thumb_key = thumbnail_key_for(key)
            self._blobs.pop(key, None)
            self._blobs.pop(thumb_key, None)
            self._staged_images.pop(key, None)
            self._key_to_listing.pop(key, None)
            self._key_to_listing.pop(key, None)

    def read_image(self, storage_key: str) -> bytes:
        if not STORAGE_KEY_PATTERN.fullmatch(storage_key):
            raise InvalidListingImageError("Некоректний ключ зображення")
        blob = self._blobs.get(storage_key)
        if blob is None:
            raise InvalidListingImageError(f"Файл {storage_key} не знайдено")
        return blob


class LocalImageStorage(BaseImageStorage):
    """Файловий адаптер ImageStorage для volume (FR-002, TM-03)."""

    def __init__(self, root_dir: Path | str) -> None:
        super().__init__()
        self._root_dir = Path(root_dir).resolve()
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._meta_cache: dict[str, ListingImage] = {}

    def _resolve_safe_path(self, key: str) -> Path:
        """Перевіряє ім'я на path traversal і повертає шлях всередині root_dir."""
        if not STORAGE_KEY_PATTERN.fullmatch(key):
            raise InvalidListingImageError("Некоректний формат ключа зображення")
        target_path = (self._root_dir / key).resolve()
        if not target_path.is_relative_to(self._root_dir):
            raise InvalidListingImageError("Спроба path traversal за межі сховища")
        return target_path

    def upload_images(self, files: Sequence[bytes]) -> list[ListingImage]:
        validate_images_count(
            files,
            min_msg="Потрібно завантажити щонайменше одне фото (FR-002)",
            max_msg=(
                f"Кількість завантажуваних фото не може "
                f"перевищувати {MAX_IMAGES_PER_LISTING}"
            ),
        )

        prepared = [(uuid4(), process_image_bytes(b)) for b in files]

        written_paths: list[Path] = []
        try:
            results: list[ListingImage] = []
            for index, (image_id, proc) in enumerate(prepared):
                main_key = f"{image_id.hex}.webp"
                thumb_key = f"{image_id.hex}_thumb.webp"
                main_path = self._resolve_safe_path(main_key)
                thumb_path = self._resolve_safe_path(thumb_key)

                main_path.write_bytes(proc.main_bytes)
                written_paths.append(main_path)

                thumb_path.write_bytes(proc.thumbnail_bytes)
                written_paths.append(thumb_path)

                item = create_listing_image_from_proc(
                    image_id=image_id,
                    storage_key=main_key,
                    proc=proc,
                    display_order=index,
                )
                self._meta_cache[main_key] = item
                results.append(item)
            return results
        except Exception:
            for p in written_paths:
                try:
                    if p.is_file():
                        p.unlink()
                except OSError:
                    pass
            raise

    def save_images(
        self, listing_id: UUID, images: Sequence[bytes | str]
    ) -> list[ListingImage]:
        validate_images_count(
            images,
            min_msg="Оголошення має містити щонайменше одне зображення (FR-002)",
            max_msg=(
                f"Кількість зображень не може " f"перевищувати {MAX_IMAGES_PER_LISTING}"
            ),
        )

        seen_keys: set[str] = set()
        resolved_items: list[ListingImage] = []
        new_files_to_write: list[tuple[Path, bytes]] = []
        new_items_to_cache: list[tuple[str, ListingImage]] = []

        for index, item in enumerate(images):
            if isinstance(item, (bytes, bytearray)):
                proc = process_image_bytes(item)
                image_id = uuid4()
                main_key = f"{image_id.hex}.webp"
                thumb_key = f"{image_id.hex}_thumb.webp"
                main_path = self._resolve_safe_path(main_key)
                thumb_path = self._resolve_safe_path(thumb_key)
                new_files_to_write.append((main_path, proc.main_bytes))
                new_files_to_write.append((thumb_path, proc.thumbnail_bytes))

                staged = create_listing_image_from_proc(
                    image_id=image_id,
                    storage_key=main_key,
                    proc=proc,
                    listing_id=listing_id,
                    display_order=index,
                )
                new_items_to_cache.append((main_key, staged))
                resolved_items.append(staged)
                seen_keys.add(main_key)
            elif isinstance(item, str):
                key = normalize_storage_key(item)
                if key in seen_keys:
                    raise InvalidListingImageError(
                        f"Дубльоване зображення {key} в одному оголошенні"
                    )
                seen_keys.add(key)

                main_path = self._resolve_safe_path(key)
                thumb_key = thumbnail_key_for(key)
                thumb_path = self._resolve_safe_path(thumb_key)

                if not main_path.is_file() or not thumb_path.is_file():
                    raise InvalidListingImageError(
                        f"Зображення {key} не знайдено на диску сховища"
                    )

                self._verify_unbound_or_owned(key, listing_id)

                existing_meta = self._meta_cache.get(key)
                img_id = (
                    existing_meta.image_id if existing_meta else UUID(key.split(".")[0])
                )
                resolved_items.append(
                    create_listing_image(
                        image_id=img_id,
                        storage_key=key,
                        listing_id=listing_id,
                        display_order=index,
                        width=existing_meta.width if existing_meta else None,
                        height=existing_meta.height if existing_meta else None,
                        thumbnail_width=(
                            existing_meta.thumbnail_width if existing_meta else None
                        ),
                        thumbnail_height=(
                            existing_meta.thumbnail_height if existing_meta else None
                        ),
                    )
                )
            else:
                raise InvalidListingImageError("Непідтримуваний тип даних зображення")

        written_paths: list[Path] = []
        try:
            for p, data in new_files_to_write:
                p.write_bytes(data)
                written_paths.append(p)
        except Exception:
            for p in written_paths:
                try:
                    if p.is_file():
                        p.unlink()
                except OSError:
                    pass
            raise

        for k, it in new_items_to_cache:
            self._meta_cache[k] = it

        return self._commit_listing_update(listing_id, resolved_items)

    def delete_images(self, storage_keys: Sequence[str]) -> None:
        for raw_key in storage_keys:
            key = (
                normalize_storage_key(raw_key)
                if not STORAGE_KEY_PATTERN.fullmatch(raw_key)
                else raw_key
            )
            thumb_key = thumbnail_key_for(key)
            for k in (key, thumb_key):
                try:
                    p = self._resolve_safe_path(k)
                    if p.is_file():
                        p.unlink()
                except Exception:
                    pass
            self._meta_cache.pop(key, None)
            self._key_to_listing.pop(key, None)

    def read_image(self, storage_key: str) -> bytes:
        p = self._resolve_safe_path(storage_key)
        if not p.is_file():
            raise InvalidListingImageError(f"Файл {storage_key} не знайдено")
        return p.read_bytes()
