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
