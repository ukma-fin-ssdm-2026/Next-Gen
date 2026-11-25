# Порівняння CI та публікацій GHCR

Когорта CI за UTC: 2026-11-18 включно — 2026-11-21 виключно. Перевірено 25.11.2026. Усі дев’ять SHA пройшли CI. Перші шість передували впровадженню публікації у #320. Успішно опубліковано всі три наступні образи, включно з образом для тегу відсічення. В обох рядах спостережень немає збоїв, тому час відновлення не визначено.

| Метрика | CI на main | Публікація образу |
|---|---:|---:|
| Успішні розгортання / за тиждень | 9 / 21.00 | 3 / 7.00 |
| Час змін (хв), медіана / середнє | 23.43 / 442.94 | 35.17 / 459.94 |
| Частка збоїв змін | 0/9 (0.0%) | 0/3 (0.0%) |
| Час відновлення (хв), медіана / середнє | — | — |

| SHA | CI | GHCR |
|---|---|---|
| `17f45c1` | [44271044609](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44271044609) (success) | — |
| `d876bf9` | [44326947724](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44326947724) (success) | — |
| `b6d4994` | [44337000738](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44337000738) (success) | — |
| `5ed2d4c` | [44345578480](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44345578480) (success) | — |
| `5cd6f31` | [44345721864](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44345721864) (success) | — |
| `ed4b168` | [44346730392](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44346730392) (success) | — |
| `0a90f7a` | [44347754814](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44347754814) (success) | [44348047588](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44348047588) (success) |
| `5385ba9` | [44378151142](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44378151142) (success) | [44378415829](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44378415829) (success) |
| `b7b05d1` | [44568859806](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44568859806) (success) | [44569404281](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44569404281) (success) |

Відтворення: `python scripts/compare_image_delivery.py --start 2026-11-18 --end 2026-11-21`.

> **Використання ШІ.** Codex допоміг оформити результати скрипта й посилання на запуски.
