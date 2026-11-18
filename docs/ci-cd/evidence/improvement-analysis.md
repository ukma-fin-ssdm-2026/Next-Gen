# Докази для плану покращень CI/CD (Lab 10, Етап 3)

Дані — той самий набір із 60 одиниць постачання, що й у [metrics-raw.md](../metrics-raw.md) (2026-10-30 — 2026-11-13, гілка `main`). Час — UTC. Значення отримано з GitHub REST API 2026-11-17.

## Як відтворити

```bash
# завдання запуску з часом створення, старту й завершення кожного завдання
gh api "repos/ukma-fin-ssdm-2026/Next-Gen/actions/runs/<run_id>/jobs?filter=all"
# відкриття PR, злиття й рецензії
gh api repos/ukma-fin-ssdm-2026/Next-Gen/pulls/<номер>
gh api repos/ukma-fin-ssdm-2026/Next-Gen/pulls/<номер>/reviews
# змінені файли PR
gh api repos/ukma-fin-ssdm-2026/Next-Gen/pulls/<номер>/files --jq '.[].filename'
# запуски Deploy API docs під час інциденту
gh api "repos/ukma-fin-ssdm-2026/Next-Gen/actions/workflows/docs.yml/runs?branch=main&created=2026-10-29..2026-10-30"
# обов'язкові перевірки гілки main
gh api repos/ukma-fin-ssdm-2026/Next-Gen/rules/branches/main
```

## 1. Черга і виконання за окремими завданнями

У `metrics-raw.md` черга — це час від створення запуску до старту **першого** завдання, а все після нього зараховано до виконання. Але завдання одного запуску чекають на вільний раннер незалежно: поки перше вже виконується, друге ще може стояти в черзі. Крім того, скасоване завдання без раннера має `started_at`, що дорівнює часу створення, і тоді черга виглядає нульовою.

Тут **виконання** — час, коли виконувалося хоча б одне завдання одиниці з призначеним раннером (об'єднання інтервалів `started_at`–`completed_at`), а **черга** — решта часу від створення першого запуску до завершення останнього завдання. Сума черги й виконання дорівнює часу CI одиниці, тож загальний час виконання змін не змінюється.

| № | PR | Статус | Черга (за завданнями) | Виконання (за завданнями) | Найдовше очікування одного завдання | Лише документація |
|---:|---:|:---:|---:|---:|---:|:---:|
| 1 | [#219](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/219) | ❌ | 3 с | 55 с | 3 с |  |
| 2 | [#220](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/220) | ❌ | 3 с | 57 с | 3 с |  |
| 3 | [#221](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/221) | ❌ | 2 с | 1 хв | 5 с | так |
| 4 | [#222](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/222) | ❌ | 46 с | 1 хв 1 с | 1 хв 13 с |  |
| 5 | [#224](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/224) | ❌ | 3 с | 56 с | 3 с | так |
| 6 | [#223](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/223) | ❌ | 3 с | 1 хв 2 с | 5 с |  |
| 7 | [#225](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/225) | ❌ | 2 хв 54 с | 1 хв 31 с | 4 хв 4 с |  |
| 8 | [#226](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/226) | ⚠️ | 45 хв 59 с | 1 хв 59 с | 47 хв 9 с |  |
| 9 | [#227](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/227) | ❌ | 55 хв 17 с | 2 хв 9 с | 56 хв 15 с |  |
| 10 | [#228](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/228) | ⚠️ | 6 хв 40 с | 1 хв 50 с | 7 хв 46 с |  |
| 11 | [#231](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/231) | ✅ | 59 с | 2 хв 28 с | 2 хв 16 с |  |
| 12 | [#230](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/230) | ✅ | 2 хв 15 с | 2 хв 48 с | 3 хв 47 с |  |
| 13 | [#233](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/233) | ✅ | 2 хв 17 с | 2 хв | 3 хв 7 с | так |
| 14 | [#234](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/234) | ✅ | 3 хв 18 с | 1 хв 6 с | 3 хв 34 с | так |
| 15 | [#235](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/235) | ✅ | 2 с | 1 хв 8 с | 3 с |  |
| 16 | [#236](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/236) | ✅ | 2 с | 1 хв 17 с | 3 с |  |
| 17 | [#237](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/237) | ✅ | 3 с | 1 хв 16 с | 4 с | так |
| 18 | [#238](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/238) | ✅ | 5 с | 2 хв 13 с | 1 хв 38 с | так |
| 19 | [#239](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/239) | ✅ | 2 с | 1 хв 17 с | 3 с | так |
| 20 | [#240](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/240) | ✅ | 2 с | 1 хв 27 с | 5 с | так |
| 21 | [#241](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/241) | ✅ | 3 с | 1 хв 35 с | 1 хв 1 с | так |
| 22 | [#242](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/242) | ✅ | 4 с | 1 хв 17 с | 4 с | так |
| 23 | [#244](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/244) | ⚠️ | 2 с | 1 хв 21 с | 3 с |  |
| 24 | [#243](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/243) | ✅ | 2 с | 1 хв 36 с | 39 с |  |
| 25 | [#245](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/245) | ✅ | 3 хв 33 с | 2 хв 20 с | 4 хв 45 с | так |
| 26 | [#246](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/246) | ✅ | 2 хв 16 с | 2 хв 30 с | 3 хв 15 с |  |
| 27 | [#247](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/247) | ✅ | 11 хв 31 с | 2 хв 2 с | 12 хв 32 с |  |
| 28 | [#248](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/248) | ✅ | 1 год 52 хв 24 с | 6 хв 17 с | 1 год 55 хв 17 с | так |
| 29 | [#249](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/249) | ✅ | 3 с | 2 хв 9 с | 4 с |  |
| 30 | [#251](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/251) | ✅ | 2 с | 1 хв 9 с | 3 с |  |
| 31 | [#252](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/252) | ✅ | 2 с | 1 хв 21 с | 20 с |  |
| 32 | [#253](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/253) | ✅ | 3 с | 1 хв 9 с | 4 с |  |
| 33 | [#262](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/262) | ✅ | 3 с | 1 хв 10 с | 6 с |  |
| 34 | [#263](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/263) | ✅ | 3 с | 1 хв 10 с | 4 с |  |
| 35 | [#264](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/264) | ✅ | 3 с | 1 хв 23 с | 3 с |  |
| 36 | [#265](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/265) | ✅ | 3 с | 1 хв 12 с | 8 с | так |
| 37 | [#266](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/266) | ✅ | 35 с | 1 хв 57 с | 1 хв 52 с | так |
| 38 | [#267](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/267) | ✅ | 29 с | 2 хв 29 с | 2 хв 15 с | так |
| 39 | [#268](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/268) | ✅ | 2 с | 1 хв 18 с | 43 с |  |
| 40 | [#269](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/269) | ✅ | 1 хв 32 с | 1 хв 16 с | 1 хв 47 с | так |
| 41 | [#270](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/270) | ✅ | 2 с | 1 хв 8 с | 3 с | так |
| 42 | [#272](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/272) | ✅ | 2 хв 21 с | 1 хв 57 с | 3 хв 31 с | так |
| 43 | [#274](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/274) | ⚠️ | 2 хв 31 с | 1 хв 21 с | 2 хв 32 с |  |
| 44 | [#275](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/275) | ✅ | 48 с | 2 хв 10 с | 2 хв 16 с |  |
| 45 | [#276](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/276) | ✅ | 2 с | 1 хв 10 с | 4 с | так |
| 46 | [#273](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/273) | ✅ | 2 с | 1 хв 9 с | 4 с | так |
| 47 | [#279](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/279) | ✅ | 2 с | 1 хв 10 с | 5 с | так |
| 48 | [#277](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/277) | ✅ | 2 с | 1 хв 9 с | 4 с | так |
| 49 | [#280](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/280) | ✅ | 2 с | 1 хв 10 с | 4 с | так |
| 50 | [#286](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/286) | ✅ | 2 с | 1 хв 10 с | 5 с |  |
| 51 | [#287](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/287) | ✅ | 4 с | 1 хв 10 с | 5 с | так |
| 52 | [#288](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/288) | ✅ | 3 с | 2 хв 17 с | 4 с |  |
| 53 | [#289](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/289) | ✅ | 2 с | 2 хв 42 с | 1 хв 18 с |  |
| 54 | [#290](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/290) | ✅ | 3 с | 2 хв 37 с | 51 с |  |
| 55 | [#291](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/291) | ✅ | 2 с | 2 хв 10 с | 5 с |  |
| 56 | [#292](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/292) | ✅ | 1 хв 16 с | 2 хв 43 с | 2 хв 34 с | так |
| 57 | [#293](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/293) | ✅ | 2 с | 1 хв 16 с | 5 с | так |
| 58 | [#294](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/294) | ✅ | 2 с | 2 хв 24 с | 5 с | так |
| 59 | [#295](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/295) | ✅ | 6 с | 3 хв 5 с | 1 хв 31 с | так |
| 60 | [#296](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/296) | ✅ | 5 с | 1 хв 27 с | 12 с | так |

| Підсумок | Сума | Медіана | Середнє | Максимум |
|---|---:|---:|---:|---:|
| Черга, 48 зелених | 2 год 27 хв 6 с | 3 с | 3 хв 4 с | 1 год 52 хв 24 с |
| Виконання, 48 зелених | 1 год 26 хв 24 с | 1 хв 25 с | 1 хв 48 с | 6 хв 17 с |
| Черга, усі 60 | 4 год 21 хв 29 с | 3 с | 4 хв 21 с | 1 год 52 хв 24 с |
| Виконання, усі 60 | 1 год 42 хв 26 с | 1 хв 21 с | 1 хв 42 с | 6 хв 17 с |

Для 48 зелених одиниць черга становить **63.0%** часу CI, виконання — **37.0%**.

## 2. Від першого коміту до злиття (48 зелених одиниць)

Якщо PR відкрито раніше за перший збережений коміт (коміти перезаписано після відкриття, як у #277 і #293), час до відкриття PR береться за 0, а рецензування рахується від першого коміту. Так дві частини разом дорівнюють часу від першого коміту до злиття.

| PR | Перший коміт → відкриття PR | Відкриття PR → перше схвалення | Відкриття PR → злиття | Лише документація |
|---:|---:|---:|---:|:---:|
| [#231](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/231) | 25 с | без схвалення | 1 хв 6 с |  |
| [#230](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/230) | 46 с | 44 хв 11 с | 44 хв 19 с |  |
| [#233](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/233) | 5 хв 42 с | 8 хв 55 с | 10 хв 6 с | так |
| [#234](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/234) | 7 с | 4 хв 8 с | 9 хв 40 с | так |
| [#235](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/235) | 25 хв 14 с | 2 хв 25 с | 13 хв 51 с |  |
| [#236](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/236) | 1 хв 6 с | 6 хв 12 с | 32 хв 18 с |  |
| [#237](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/237) | 58 с | 1 хв 27 с | 1 хв 35 с | так |
| [#238](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/238) | 1 хв 16 с | 9 хв 10 с | 9 хв 43 с | так |
| [#239](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/239) | 2 хв 35 с | 1 хв 3 с | 2 хв 54 с | так |
| [#240](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/240) | 55 с | 2 хв 7 с | 2 хв 43 с | так |
| [#241](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/241) | 1 хв 4 с | 8 хв 11 с | 8 хв 24 с | так |
| [#242](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/242) | 6 хв 7 с | 18 с | 2 хв 3 с | так |
| [#243](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/243) | 11 год 19 хв 38 с | 16 год 30 хв 19 с | 20 год 37 хв 10 с |  |
| [#245](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/245) | 5 с | 22 хв | 22 хв 16 с | так |
| [#246](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/246) | 10 хв 17 с | 32 хв 9 с | 32 хв 31 с |  |
| [#247](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/247) | 10 хв 32 с | 26 хв 4 с | 43 хв 5 с |  |
| [#248](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/248) | 40 с | 49 с | 3 год 20 хв 21 с | так |
| [#249](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/249) | 20 хв 48 с | 12 год 11 хв 34 с | 12 год 11 хв 55 с |  |
| [#251](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/251) | 22 с | 15 хв 23 с | 15 хв 32 с |  |
| [#252](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/252) | 14 хв 12 с | 44 хв 18 с | 44 хв 24 с |  |
| [#253](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/253) | 1 хв 45 с | 3 хв 31 с | 3 хв 41 с |  |
| [#262](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/262) | 6 хв 2 с | 4 год 14 хв 25 с | 4 год 14 хв 32 с |  |
| [#263](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/263) | 20 хв 21 с | 5 год 1 хв 50 с | 5 год 1 хв 56 с |  |
| [#264](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/264) | 3 хв 10 с | 40 хв 11 с | 40 хв 31 с |  |
| [#265](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/265) | 55 с | 1 хв 51 с | 1 хв 58 с | так |
| [#266](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/266) | 5 хв 57 с | 2 хв 30 с | 2 хв 35 с | так |
| [#267](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/267) | 8 с | 23 с | 6 хв 39 с | так |
| [#268](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/268) | 1 хв 43 с | 27 с | 1 хв 25 с |  |
| [#269](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/269) | 1 хв 55 с | 24 с | 1 хв 50 с | так |
| [#270](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/270) | 36 с | 22 с | 9 год 22 хв 38 с | так |
| [#272](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/272) | 3 хв 1 с | 4 год 39 хв 21 с | 4 год 39 хв 30 с | так |
| [#275](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/275) | 17 хв 24 с | 36 хв 45 с | 36 хв 54 с |  |
| [#276](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/276) | 1 хв 1 с | 8 хв 34 с | 8 хв 42 с | так |
| [#273](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/273) | 4 хв 30 с | 4 год 34 хв 48 с | 4 год 34 хв 58 с | так |
| [#279](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/279) | 15 хв 52 с | 3 хв 12 с | 3 хв 21 с | так |
| [#277](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/277) | 0 с | 4 хв 39 с | 4 хв 49 с | так |
| [#280](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/280) | 5 хв 32 с | 28 с | 1 хв 26 с | так |
| [#286](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/286) | 2 хв 10 с | 1 год 3 хв 27 с | 1 год 3 хв 34 с |  |
| [#287](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/287) | 1 хв 34 с | 1 год 32 хв 2 с | 1 год 32 хв 12 с | так |
| [#288](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/288) | 1 хв 44 с | 1 год 2 хв 9 с | 1 год 2 хв 17 с |  |
| [#289](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/289) | 5 хв 41 с | 2 хв 57 с | 3 хв 40 с |  |
| [#290](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/290) | 20 хв 55 с | 30 хв 56 с | 37 хв 46 с |  |
| [#291](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/291) | 12 хв 22 с | 23 хв 12 с | 40 хв 4 с |  |
| [#292](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/292) | 27 с | 4 хв 14 с | 8 хв 23 с | так |
| [#293](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/293) | 0 с | 9 хв 10 с | 9 хв 18 с | так |
| [#294](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/294) | 5 с | 11 хв 45 с | 11 хв 51 с | так |
| [#295](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/295) | 26 с | 1 хв 21 с | 33 хв 37 с | так |
| [#296](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/296) | 2 хв 58 с | 20 год 8 хв 23 с | 20 год 8 хв 29 с | так |

| Підсумок | Сума | Медіана | Середнє | Максимум |
|---|---:|---:|---:|---:|
| Перший коміт → відкриття PR | 15 год 21 хв 3 с | 1 хв 50 с | 19 хв 11 с | 11 год 19 хв 38 с |
| Відкриття PR → перше схвалення (47 PR) | 3 д 5 год 54 хв | 8 хв 55 с | 1 год 39 хв 27 с | 20 год 8 хв 23 с |
| Відкриття PR → злиття | 4 д 1 год 4 хв 32 с | 14 хв 42 с | 2 год 1 хв 21 с | 20 год 37 хв 10 с |

## 3. Злиття лише з документацією

«Лише документація» — PR, усі файли якого лежать у `docs/` (крім `docs/api/`, з якого генерується OpenAPI), `Labs/`, `uml/` або мають розширення `.md` чи `.txt`. Таких одиниць **29 із 60**: #221, #224, #233, #234, #237, #238, #239, #240, #241, #242, #245, #248, #265, #266, #267, #269, #270, #272, #276, #273, #279, #277, #280, #287, #292, #293, #294, #295, #296. Кожна з них запускала повний `CI` і `Deploy API docs`: разом 50 хв 36 с виконання з 1 год 42 хв 26 с і 2 год 8 хв 43 с черги з 4 год 21 хв 29 с.

## 4. Запуски `Deploy API docs` під час інциденту 29–30 жовтня

Сім перших падінь сталися ще до початку періоду вимірювання (2026-10-30), тому в `metrics-raw.md` їх немає.

| Запуск | Завершено | Результат | Злиття |
|---|---|---|---|
| [40928617078](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/40928617078) | 2026-10-29 18:13:59 | ❌ failure | [#212](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/212) |
| [40932347355](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/40932347355) | 2026-10-29 18:36:31 | ❌ failure | [#213](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/213) |
| [40934038298](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/40934038298) | 2026-10-29 18:47:48 | ❌ failure | [#214](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/214) |
| [40953287663](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/40953287663) | 2026-10-29 20:55:50 | ❌ failure | [#215](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/215) |
| [40964291161](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/40964291161) | 2026-10-29 22:29:17 | ❌ failure | [#216](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/216) |
| [40969829565](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/40969829565) | 2026-10-29 23:02:49 | ❌ failure | [#217](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/217) |
| [40972202443](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/40972202443) | 2026-10-29 23:26:30 | ❌ failure | [#218](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/218) |
| [40977034363](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/40977034363) | 2026-10-30 00:02:15 | ❌ failure | [#219](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/219) |
| [41025302717](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41025302717) | 2026-10-30 08:16:31 | ❌ failure | [#220](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/220) |
| [41027868569](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41027868569) | 2026-10-30 08:39:30 | ❌ failure | [#221](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/221) |
| [41030154983](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41030154983) | 2026-10-30 09:01:02 | ❌ failure | [#222](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/222) |
| [41039331249](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41039331249) | 2026-10-30 10:15:19 | ❌ failure | [#224](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/224) |
| [41047471209](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41047471209) | 2026-10-30 11:21:36 | ❌ failure | [#223](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/223) |
| [41056744971](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41056744971) | 2026-10-30 12:41:57 | ❌ failure | [#225](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/225) |
| [41059064061](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41059064061) | 2026-10-30 13:00:17 | ⚠️ cancelled | [#226](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/226) |
| [41059651717](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41059651717) | 2026-10-30 13:08:23 | ❌ failure | [#227](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/227) |
| [41080526550](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41080526550) | 2026-10-30 15:57:00 | ⚠️ cancelled | [#228](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/228) |
| [41082485308](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41082485308) | 2026-10-30 15:41:20 | ✅ success | [#231](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/231) — виправлення |

Лог першого падіння ([40928617078](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/40928617078)) і всіх наступних закінчується однаково:

```text
from PIL import Image, ImageOps, UnidentifiedImageError
ModuleNotFoundError: No module named 'PIL'
```

## 5. Обов'язкові перевірки гілки `main` (ruleset, 2026-11-17)

`test`, `SonarCloud Code Analysis`, `Reliability tests`; `strict_required_status_checks_policy: false`. Завдання `Alembic migration check (PostgreSQL 16)` і робочий процес `Deploy API docs` до обов'язкових не входять, а `Deploy API docs` на pull request взагалі не запускається.

