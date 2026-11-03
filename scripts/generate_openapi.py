"""
Скрипт автоматичної генерації специфікації OpenAPI у форматі YAML.
Зчитує схему безпосередньо з FastAPI застосунку (Code-First підхід)
та записує результат у docs/api/openapi-generated.yaml.
"""

from pathlib import Path
import sys
import yaml

# Додаємо корінь проєкту в sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.api.main import app  # noqa: E402

# Маркер для release-please (generic updater): під час релізу він оновлює
# номер версії саме в цьому рядку, тож закомічена специфікація лишається
# актуальною без повторної генерації в CI.
RELEASE_MARKER = "x-release-please-version"


def render_openapi_yaml() -> str:
    """Повертає OpenAPI у YAML з маркером релізу на рядку `info.version`."""
    openapi_schema = app.openapi()
    text = yaml.dump(openapi_schema, allow_unicode=True, sort_keys=False)
    version_line = f"\n  version: {openapi_schema['info']['version']}\n"
    marked_line = version_line.rstrip("\n") + f" # {RELEASE_MARKER}\n"
    return text.replace(version_line, marked_line, 1)


def generate_openapi_yaml():
    output_dir = ROOT_DIR / "docs" / "api"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "openapi-generated.yaml"

    # Записуємо у YAML файл з коректним кодуванням UTF-8
    output_file.write_text(render_openapi_yaml(), encoding="utf-8")

    print(f"[OK] Специфікація OpenAPI успішно згенерована: {output_file}")


if __name__ == "__main__":
    generate_openapi_yaml()
