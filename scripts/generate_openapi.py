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


def generate_openapi_yaml():
    output_dir = ROOT_DIR / "docs" / "api"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "openapi-generated.yaml"

    # Отримуємо згенеровану FastAPI OpenAPI схему (dict)
    openapi_schema = app.openapi()

    # Записуємо у YAML файл з коректним кодуванням UTF-8
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(openapi_schema, f, allow_unicode=True, sort_keys=False)

    print(f"[OK] Специфікація OpenAPI успішно згенерована: {output_file}")


if __name__ == "__main__":
    generate_openapi_yaml()
