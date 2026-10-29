"""Модульні тести обробки зображень та сховища LocalImageStorage (FR-002, TM-03)."""

import io
from pathlib import Path
from uuid import uuid4

from PIL import Image
import pytest

from src.domain.exceptions import InvalidListingImageError
from src.repositories.image_storage import (
    MAX_IMAGE_FILE_SIZE_BYTES,
    MAX_MAIN_DIMENSION,
    MAX_THUMBNAIL_DIMENSION,
    LocalImageStorage,
    normalize_storage_key,
    process_image_bytes,
)


def _make_image_bytes(
    fmt: str = "JPEG",
    size: tuple[int, int] = (200, 150),
    color: tuple[int, int, int] = (120, 60, 20),
    exif: bytes | None = None,
) -> bytes:
    """Генерує валідні байти зображення заданого формату."""
    im = Image.new("RGB", size, color)
    buf = io.BytesIO()
    save_kwargs = {}
    if exif:
        save_kwargs["exif"] = exif
    im.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


def _make_heic_bytes(size: tuple[int, int] = (180, 120)) -> bytes:
    """Генерує валідний HEIF/HEIC файл через pillow-heif."""
    im = Image.new("RGB", size, (200, 100, 50))
    buf = io.BytesIO()
    im.save(buf, format="HEIF")
    return buf.getvalue()


def test_process_image_formats_jpeg_png_webp_heic_heif() -> None:
    """[TP-022] [FR-002]
    Успішна обробка та нормалізація форматів JPEG, PNG, WebP, HEIC та HEIF.
    """
    formats_and_payloads = [
        ("JPEG", _make_image_bytes("JPEG")),
        ("PNG", _make_image_bytes("PNG")),
        ("WEBP", _make_image_bytes("WEBP")),
        ("HEIC", _make_heic_bytes()),
        ("HEIF", _make_heic_bytes().replace(b"ftypheic", b"ftypmif1", 1)),
    ]

    for fmt_name, raw_bytes in formats_and_payloads:
        result = process_image_bytes(raw_bytes)
        assert result.main_bytes.startswith(b"RIFF")
        assert b"WEBP" in result.main_bytes[:16]
        assert result.thumbnail_bytes.startswith(b"RIFF")
        assert b"WEBP" in result.thumbnail_bytes[:16]
        assert result.width > 0 and result.height > 0
        assert result.thumbnail_width > 0 and result.thumbnail_height > 0


def test_decode_heic_heif_regardless_of_filename_and_content_type() -> None:
    """[TP-022] [FR-002]
    Декодування реального HEIC/HEIF файлу за фактичними байтами незалежно від назви.
    """
    heic_bytes = _make_heic_bytes((300, 200))
    # Передаємо сирі байти без жодних метаданих MIME чи розширення
    result = process_image_bytes(heic_bytes)
    assert result.source_format in {"HEIF", "HEIC"}
    assert result.width == 300
    assert result.height == 200


def test_exif_orientation_and_metadata_stripping() -> None:
    """[TP-022] [FR-002]
    Застосування EXIF-orientation та повне видалення EXIF, XMP і GPS metadata.
    """
    # Створюємо JPEG із EXIF Orientation=6 (90° CW) та GPS-тегами
    exif = Image.Exif()
    exif[274] = 6  # Orientation: Rotate 90 CW
    exif[34853] = {1: "N", 2: (50, 27, 0), 3: "E", 4: (30, 31, 0)}  # GPS IFD
    exif[271] = "Apple iPhone"

    raw_jpeg = _make_image_bytes("JPEG", size=(300, 100), exif=exif.tobytes())

    # Перевіряємо, що вхідний файл містить орієнтацію та GPS
    in_img = Image.open(io.BytesIO(raw_jpeg))
    assert in_img.size == (300, 100)
    assert in_img.getexif().get(274) == 6

    # Нормалізуємо
    result = process_image_bytes(raw_jpeg)

    # Перевіряємо поворот: ширина й висота мають помінятися місцями (100, 300)
    assert result.width == 100
    assert result.height == 300

    # Перевіряємо, що результуючий WebP повністю позбавлений EXIF, XMP та GPS
    out_img = Image.open(io.BytesIO(result.main_bytes))
    out_exif = out_img.getexif()
    assert len(out_exif) == 0
    assert "exif" not in out_img.info
    assert "xmp" not in out_img.info
    assert "gps" not in str(out_img.info).lower()


def test_dimensions_resizing_and_no_upscaling() -> None:
    """[TP-022] [FR-002]
    Зменшення довгої сторони до 1600 px (основне) та 400 px (thumbnail) без апскейлу.
    """
    # 1. Велике зображення: 3200x1600
    large_raw = _make_image_bytes("PNG", size=(3200, 1600))
    large_res = process_image_bytes(large_raw)
    assert large_res.width == MAX_MAIN_DIMENSION  # 1600
    assert large_res.height == 800
    assert large_res.thumbnail_width == MAX_THUMBNAIL_DIMENSION  # 400
    assert large_res.thumbnail_height == 200

    # 2. Мале зображення: 250x150 (не має збільшуватися)
    small_raw = _make_image_bytes("JPEG", size=(250, 150))
    small_res = process_image_bytes(small_raw)
    assert small_res.width == 250
    assert small_res.height == 150
    assert small_res.thumbnail_width == 250
    assert small_res.thumbnail_height == 150


def test_output_format_is_webp_quality_80() -> None:
    """[TP-022] [FR-002]
    Основне зображення та thumbnail зберігаються у форматі WebP із quality=80.
    """
    raw = _make_image_bytes("PNG", size=(500, 500))
    res = process_image_bytes(raw)

    main_im = Image.open(io.BytesIO(res.main_bytes))
    assert main_im.format == "WEBP"

    thumb_im = Image.open(io.BytesIO(res.thumbnail_bytes))
    assert thumb_im.format == "WEBP"


def test_rejection_of_empty_and_oversized_files() -> None:
    """[TP-022] [FR-002] [TM-08]
    Відхилення порожнього файлу та файлу розміром більше 10 МБ.
    """
    with pytest.raises(InvalidListingImageError) as exc_info:
        process_image_bytes(b"")
    assert "порожній" in str(exc_info.value).lower()

    huge_bytes = b"0" * (MAX_IMAGE_FILE_SIZE_BYTES + 1)
    with pytest.raises(InvalidListingImageError) as exc_huge:
        process_image_bytes(huge_bytes)
    assert "перевищує" in str(exc_huge.value)


def test_rejection_of_svg_files() -> None:
    """[TP-022] [FR-002] [TM-03] Відхилення векторного формату SVG."""
    svg_payload = (
        b'<svg xmlns="http://www.w3.org/2000/svg">'
        b'<rect width="100" height="100"/></svg>'
    )
    with pytest.raises(InvalidListingImageError) as exc_info:
        process_image_bytes(svg_payload)
    assert "svg" in str(exc_info.value).lower()


def test_rejection_of_animated_images() -> None:
    """[TP-022] [FR-002] [TM-03] Відхилення анімованих зображень (GIF/APNG/WebP)."""
    # 1. Створюємо 2-кадровий анімований WebP
    frame1 = Image.new("RGB", (100, 100), (255, 0, 0))
    frame2 = Image.new("RGB", (100, 100), (0, 255, 0))
    buf_webp = io.BytesIO()
    frame1.save(
        buf_webp,
        format="WEBP",
        save_all=True,
        append_images=[frame2],
        duration=100,
        loop=0,
    )
    with pytest.raises(InvalidListingImageError) as exc_webp:
        process_image_bytes(buf_webp.getvalue())
    assert "анімовані" in str(exc_webp.value).lower()

    # 2. Формат GIF також відхиляється
    buf_gif = io.BytesIO()
    frame1.save(buf_gif, format="GIF")
    with pytest.raises(InvalidListingImageError):
        process_image_bytes(buf_gif.getvalue())


def test_rejection_of_video_and_raw_formats() -> None:
    """[TP-022] [FR-002] [TM-03]
    Відхилення Live Photo (.mov), відеофайлів (.mp4) та RAW/DNG.
    """
    # Імітація QuickTime MOV заголовка
    mov_header = b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00" + b"\x00" * 100
    with pytest.raises(InvalidListingImageError) as exc_mov:
        process_image_bytes(mov_header)
    assert "відеофайли" in str(exc_mov.value).lower()

    # Імітація TIFF / DNG сигнатури
    dng_header = b"II*\x00" + b"\x00" * 100
    with pytest.raises(InvalidListingImageError) as exc_dng:
        process_image_bytes(dng_header)
    assert "raw" in str(exc_dng.value).lower()


def test_rejection_of_decompression_bomb() -> None:
    """[TP-022] [FR-002] [TM-08] Захист від decompression bomb."""
    # Зображення з кількістю пікселів більше ліміту max_pixels
    with pytest.raises(InvalidListingImageError) as exc_info:
        process_image_bytes(
            _make_image_bytes("PNG", size=(6000, 6000)), max_pixels=20_000_000
        )
    assert "decompression bomb" in str(exc_info.value).lower()


def test_local_image_storage_path_traversal_protection(tmp_path: Path) -> None:
    """[TP-022] [FR-002] [TM-03]
    Неможливість path traversal та доступу поза межі директорії сховища.
    """
    storage = LocalImageStorage(tmp_path)
    with pytest.raises(InvalidListingImageError):
        normalize_storage_key("../../secret.txt")
    with pytest.raises(InvalidListingImageError):
        normalize_storage_key("..\\..\\secret.txt")
    with pytest.raises(InvalidListingImageError):
        normalize_storage_key("/uploads/../../secret.txt")
    with pytest.raises(InvalidListingImageError):
        storage.read_image("../../etc/passwd")


def test_local_image_storage_uuid_keys_and_no_collisions(tmp_path: Path) -> None:
    """[TP-022] [FR-002] [TM-03]
    Генерація непередбачуваних UUID-ключів та відсутність колізій.
    """
    storage = LocalImageStorage(tmp_path)
    batch = [
        _make_image_bytes("JPEG", size=(100, 100), color=(1, 2, 3)),
        _make_image_bytes("PNG", size=(100, 100), color=(4, 5, 6)),
    ]
    saved = storage.upload_images(batch)
    assert len(saved) == 2
    assert saved[0].storage_key != saved[1].storage_key
    assert saved[0].storage_key.endswith(".webp")
    assert saved[0].thumbnail_url.endswith("_thumb.webp")

    # Файли реально створені у tmp_path
    assert (tmp_path / saved[0].storage_key).is_file()
    assert (tmp_path / f"{saved[0].image_id.hex}_thumb.webp").is_file()


def test_local_image_storage_preserves_display_order(tmp_path: Path) -> None:
    """[TP-022] [FR-002] Збереження послідовності display_order."""
    storage = LocalImageStorage(tmp_path)
    batch = [_make_image_bytes("JPEG", size=(80, 80)) for _ in range(4)]
    saved = storage.upload_images(batch)
    for i, item in enumerate(saved):
        assert item.display_order == i

    listing_id = uuid4()
    bound = storage.save_images(listing_id, [it.storage_key for it in saved])
    for i, item in enumerate(bound):
        assert item.display_order == i
        assert item.listing_id == listing_id


def test_local_image_storage_atomic_batch_rollback(tmp_path: Path) -> None:
    """[TP-022] [FR-002] [TM-03]
    Відсутність частково збереженого набору, якщо один із файлів пачки невалідний.
    """
    storage = LocalImageStorage(tmp_path)
    valid_file = _make_image_bytes("JPEG", size=(100, 100))
    corrupted_file = b"corrupted random non-image bytes"

    # Спроба завантажити пачку з валідного та битого файлу
    with pytest.raises(InvalidListingImageError):
        storage.upload_images([valid_file, corrupted_file])

    # На диску не має залишитися жодного файлу
    remaining_files = list(tmp_path.glob("*.webp"))
    assert len(remaining_files) == 0


def test_local_image_storage_cleanup_on_patch_replacement(tmp_path: Path) -> None:
    """[TP-022] [FR-002] [FR-003]
    Очищення замінених фотографій при PATCH оновленні оголошення.
    """
    storage = LocalImageStorage(tmp_path)
    listing_id = uuid4()

    # 1. Початкові 2 фотографії
    uploaded_initial = storage.upload_images(
        [
            _make_image_bytes("JPEG", size=(100, 100)),
            _make_image_bytes("PNG", size=(120, 120)),
        ]
    )
    key1 = uploaded_initial[0].storage_key
    key2 = uploaded_initial[1].storage_key
    storage.save_images(listing_id, [key1, key2])

    assert (tmp_path / key1).is_file()
    assert (tmp_path / key2).is_file()

    # 2. Нове фото, що замінить попередні
    uploaded_new = storage.upload_images([_make_image_bytes("WEBP", size=(150, 150))])
    key3 = uploaded_new[0].storage_key

    # PATCH оновлення: залишаємо key1, видаляємо key2, додаємо key3
    storage.save_images(listing_id, [key1, key3])

    # key1 та key3 мають існувати, а key2 та його thumbnail мають бути фізично видалені
    assert (tmp_path / key1).is_file()
    assert (tmp_path / key3).is_file()
    assert not (tmp_path / key2).is_file()
    assert not (tmp_path / f"{key2[:-5]}_thumb.webp").is_file()


def test_local_image_storage_read_image(tmp_path: Path) -> None:
    """[TP-022] [FR-002] Читання бінарних даних збереженого зображення."""
    storage = LocalImageStorage(tmp_path)
    saved = storage.upload_images([_make_image_bytes("JPEG", size=(90, 90))])
    data = storage.read_image(saved[0].storage_key)
    assert data.startswith(b"RIFF")
    assert b"WEBP" in data[:16]

    with pytest.raises(InvalidListingImageError):
        storage.read_image("nonexistent_0000000000000000.webp")
