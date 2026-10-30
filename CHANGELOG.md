# Changelog

Формат: [Keep a Changelog](https://keepachangelog.com/uk/1.1.0/), версіонування: [SemVer](https://semver.org/lang/uk/).

## [1.0.1] - 2026-10-30

### Refactoring

- Email-regex у `frontend/src/contactLinks.ts` замінено розбором рядка без backtracking (Replace Algorithm); поведінка збережена, перевірено на >10 000 рядків.
- Функцію `confirm` кадрування фото розбито на `paintGaps` і `CropFill` (Extract Method).
- Кадр обрізання фото і галерею переведено з `div` з `tabIndex` на семантичні `button` і `section` (Replace Element with Semantic Element).
- Встановлення залежностей у CI і документації зафіксовано lock-файлами з хешами: `requirements-ci.lock`, `requirements.lock`, `pip install --require-hashes --only-binary :all:`.
- Згенеровані файли (`htmlcov/`, `docs/api/openapi-generated.yaml`) виключено з аналізу SonarCloud (`sonar-project.properties`) і з git.

### Changed

- Версію синхронізовано у `pyproject.toml`, `src/api/main.py`, `docs/api/openapi-generated.yaml`, `frontend/package.json` та `frontend/package-lock.json`.
- CI показує підсумок покриття тестами у Job Summary.
