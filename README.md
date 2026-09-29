[![CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/workflows/ci.yml/badge.svg)](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/workflows/ci.yml)
# Baraholka NaUKMA

Командний проєкт з курсу SSDM 2026.

## Команда 

- Repo Maintainer - Артем Солодкий
- Documentation Lead - Остапенко Євгеній
- Issue Tracker Lead - Солонина Богдан
- CI Maintainer - Чернявський Данііл

## Стратегія роботи з гілками - GitHub Flow

- `main` містить стабільну версію проєкту.
- Нова робота виконується в окремих гілках.
- Зміни додаються до `main` через Pull Request.
- Прямі push у `main` обмежені.

### Назви гілок

- `feature/...` - нова функціональність
- `fix/...` - виправлення помилок
- `docs/...` - зміни в документації
- `ci/...` - зміни, пов'язані з CI/CD
- `loom-videos` - файли з посиланням на відео до лабораторних

## Артефакти вимог

- [Вимоги (FR та NFR)](docs/requirements/requirements.md) - функціональні вимоги та вимірювані NFR за стандартом ISO 25010.
- [Користувацькі історії](docs/requirements/user-stories.md) - історії користувачів із критеріями прийняття.
- [Матриця простежуваності (RTM)](docs/requirements/rtm.md) - зв'язок між історіями, NFR та тестами.
- [Сценарії використання (Use Cases)](docs/requirements/use-cases.md) - детальні сценарії взаємодії користувача із системою.

## Архітектура та проєктування

- [Високорівневий дизайн (HLD)](docs/architecture/high-level-design.md) - архітектурний стиль, опис системи та інтерфейсів.
- [Матриця простежуваності архітектури](docs/architecture/traceability-matrix.md) - відображення вимог на компоненти та сценарії якості.
- [Модель даних](docs/architecture/data-model.md) - схема бази даних (ER) із позначенням чутливих даних.
- [Модель загроз STRIDE](docs/architecture/threat-model.md) - аналіз меж довіри, ризиків та контрзаходів.
- [Архітектурні рішення (ADR)](docs/architecture/decisions/) - реєстр ключових технічних рішень проєкту.
- [UML-діаграми](docs/architecture/uml/) - сирцеві файли діаграм компонентів, послідовності та розгортання.
