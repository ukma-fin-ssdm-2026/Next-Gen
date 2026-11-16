# Сирі метрики конвеєра CI/CD

## Методика

- **Гілка:** `main`.
- **Період спостереження:** 2026-10-30 — 2026-11-13 включно (15 календарних днів).
- **Одиниця постачання:** один merge-коміт запиту на злиття у `main`, а не окремий запуск робочого процесу.
- **Автоматичні перевірки одиниці:** `CI` і `Deploy API docs`.
- **Статус:** ✅ — обидва робочі процеси успішні; ❌ — хоча б один завершився помилкою; ⚠️ — помилки немає, але хоча б один робочий процес скасований.
- **Час очікування:** від створення першого запуску до старту першого завдання.
- **Час виконання:** від старту першого завдання до завершення останнього завдання цієї одиниці.
- **Час:** UTC, формат `YYYY-MM-DD HH:MM:SS`.
- **Виключено:** ручні `Performance`/`Release` та окремі робочі процеси Dependabot, бо вони не є самостійними постачаннями застосунку.
- **Артефакт сирих доказів (JSON):** усі 60 одиниць і 120 запусків GitHub Actions збережено у [evidence/main-runs-2026-10-30-to-2026-11-13.json](evidence/main-runs-2026-10-30-to-2026-11-13.json) (схема та команди відтворення — у [evidence/README.md](evidence/README.md)).

За період зафіксовано **60 із 60 автоматичних одиниць постачання**: 48 успішних, 8 із помилкою та 4 скасовані. У таблиці немає вибірки чи пропусків. На 31 жовтня, 6–9 листопада і 13 листопада merge-запусків у `main` не було; остання одиниця завершилася 12 листопада.

## Усі одиниці постачання

| № | Коміт | Запит на злиття | Перший коміт | Завершення | Час очікування | Час виконання | Статус | Докази / примітка |
|---:|---|---:|---|---|---:|---:|:---:|---|
| 1 | `7863abb` | [#219](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/219) | 2026-10-29 22:58:59 | 2026-10-30 00:02:47 | 3 с | 55 с | ❌ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/40977034363), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/40977034184); docs failed |
| 2 | `a40fbad` | [#220](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/220) | 2026-10-30 00:04:44 | 2026-10-30 08:17:06 | 3 с | 57 с | ❌ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41025302679), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41025302717); docs failed |
| 3 | `5752dc7` | [#221](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/221) | 2026-10-30 08:26:23 | 2026-10-30 08:40:04 | 2 с | 1 хв | ❌ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41027868569), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41027868465); docs failed |
| 4 | `e22b956` | [#222](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/222) | 2026-10-30 08:43:14 | 2026-10-30 09:01:13 | 46 с | 1 хв 1 с | ❌ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41030154983), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41030154974); docs failed |
| 5 | `626d519` | [#224](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/224) | 2026-10-30 09:36:45 | 2026-10-30 10:15:53 | 3 с | 56 с | ❌ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41039331720), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41039331249); docs failed |
| 6 | `cf057e2` | [#223](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/223) | 2026-10-30 09:22:49 | 2026-10-30 11:22:14 | 3 с | 1 хв 2 с | ❌ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41047471250), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41047471209); docs failed |
| 7 | `65c7532` | [#225](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/225) | 2026-10-30 11:40:15 | 2026-10-30 12:41:56 | 2 хв 54 с | 1 хв 31 с | ❌ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41056744968), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41056744971); docs failed |
| 8 | `2ba1d4a` | [#226](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/226) | 2026-10-30 12:28:18 | 2026-10-30 13:43:35 | 1 с | 47 хв 57 с | ⚠️ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41059064061), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41059063994); docs cancelled |
| 9 | `71a41c4` | [#227](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/227) | 2026-10-30 12:30:11 | 2026-10-30 13:57:42 | 7 хв 42 с | 49 хв 44 с | ❌ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41059651717), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41059651785); docs failed |
| 10 | `f933af4` | [#228](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/228) | 2026-10-30 14:03:15 | 2026-10-30 15:56:59 | 6 хв 43 с | 25 хв 8 с | ⚠️ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41080526550), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41080526461); docs cancelled |
| 11 | `0dcf011` | [#231](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/231) | 2026-10-30 15:36:19 | 2026-10-30 15:41:20 | 14 с | 3 хв 13 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41082485308), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41082485285); перше відновлення |
| 12 | `c2385d9` | [#230](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/230) | 2026-10-30 15:11:50 | 2026-10-30 16:02:01 | 1 хв 43 с | 3 хв 20 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41085384351), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41085384370) |
| 13 | `b1d03da` | [#233](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/233) | 2026-10-30 16:01:41 | 2026-10-30 16:21:49 | 2 хв 17 с | 2 хв | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41088537561), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41088537773) |
| 14 | `d20bbe8` | [#234](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/234) | 2026-10-30 16:52:06 | 2026-10-30 17:06:20 | 3 хв 18 с | 1 хв 6 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41095204190), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41095204499) |
| 15 | `83c0bcc` | [#235](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/235) | 2026-10-30 16:29:13 | 2026-10-30 17:09:31 | 2 с | 1 хв 8 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41096167570), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41096167382) |
| 16 | `4c8738d` | [#236](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/236) | 2026-10-30 21:38:32 | 2026-10-30 22:13:20 | 2 с | 1 хв 17 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41136503278), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41136503445) |
| 17 | `807aa51` | [#237](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/237) | 2026-10-30 22:13:57 | 2026-10-30 22:17:51 | 3 с | 1 хв 16 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41137011803), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41137011650) |
| 18 | `6836098` | [#238](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/238) | 2026-10-30 22:19:08 | 2026-10-30 22:32:28 | 2 с | 2 хв 16 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41138535949), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41138535997) |
| 19 | `5bebfea` | [#239](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/239) | 2026-10-30 22:34:32 | 2026-10-30 22:41:23 | 2 с | 1 хв 17 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41139623587), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41139623745) |
| 20 | `744826d` | [#240](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/240) | 2026-10-30 22:42:01 | 2026-10-30 22:47:11 | 2 с | 1 хв 27 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41140226494), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41140226463) |
| 21 | `1a1d8ab` | [#241](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/241) | 2026-10-30 22:46:54 | 2026-10-30 22:58:03 | 3 с | 1 хв 35 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41141352996), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41141353092) |
| 22 | `93179d5` | [#242](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/242) | 2026-10-30 22:51:22 | 2026-10-30 23:00:56 | 4 с | 1 хв 17 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41141663330), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41141663243) |
| 23 | `918d08a` | [#244](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/244) | 2026-11-01 01:51:46 | 2026-11-01 06:50:13 | 2 с | 1 хв 21 с | ⚠️ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41282314515), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41282314559); docs cancelled |
| 24 | `c1a0113` | [#243](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/243) | 2026-10-30 22:52:14 | 2026-11-01 06:50:43 | 2 с | 1 хв 36 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41282329409), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41282329444) |
| 25 | `c1efd5b` | [#245](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/245) | 2026-11-01 10:48:40 | 2026-11-01 11:16:57 | 3 хв 20 с | 2 хв 33 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41300753796), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41300753833) |
| 26 | `0abb669` | [#246](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/246) | 2026-11-01 12:45:24 | 2026-11-01 13:33:02 | 2 хв 12 с | 2 хв 34 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41311405828), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41311405851) |
| 27 | `7f65f8e` | [#247](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/247) | 2026-11-01 13:49:46 | 2026-11-01 14:56:58 | 1 хв 14 с | 12 хв 19 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41317592925), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41317592813) |
| 28 | `e2a6838` | [#248](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/248) | 2026-11-01 15:51:04 | 2026-11-01 21:10:49 | 20 хв 44 с | 1 год 37 хв 57 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41340528492), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41340528461) |
| 29 | `2591f9d` | [#249](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/249) | 2026-11-01 20:56:11 | 2026-11-02 09:31:08 | 3 с | 2 хв 9 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41421001189), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41421001135) |
| 30 | `9388dde` | [#251](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/251) | 2026-11-02 10:11:46 | 2026-11-02 10:28:56 | 2 с | 1 хв 9 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41428993795), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41428993819) |
| 31 | `ba6799a` | [#252](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/252) | 2026-11-02 11:15:24 | 2026-11-02 12:15:26 | 2 с | 1 хв 21 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41443004979), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41443004880) |
| 32 | `c8a7bcd` | [#253](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/253) | 2026-11-03 16:38:41 | 2026-11-03 16:45:21 | 3 с | 1 хв 9 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41677211521), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41677211431) |
| 33 | `5abdb90` | [#262](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/262) | 2026-11-04 15:56:36 | 2026-11-04 20:18:25 | 3 с | 1 хв 10 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41905144703), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41905144855) |
| 34 | `0df73e1` | [#263](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/263) | 2026-11-04 15:59:40 | 2026-11-04 21:23:14 | 3 с | 1 хв 10 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41915423503), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41915423395) |
| 35 | `129380f` | [#264](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/264) | 2026-11-04 21:32:07 | 2026-11-04 22:17:17 | 3 с | 1 хв 23 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41923715409), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41923715471) |
| 36 | `81bf023` | [#265](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/265) | 2026-11-04 22:20:06 | 2026-11-04 22:24:16 | 3 с | 1 хв 12 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41924786541), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41924786436) |
| 37 | `89e7904` | [#266](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/266) | 2026-11-04 22:19:34 | 2026-11-04 22:30:41 | 30 с | 2 хв 2 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41925528194), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41925528174) |
| 38 | `b6193f0` | [#267](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/267) | 2026-11-04 22:44:42 | 2026-11-04 22:54:30 | 29 с | 2 хв 29 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41928892510), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41928892881) |
| 39 | `9834d57` | [#268](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/268) | 2026-11-04 22:59:26 | 2026-11-04 23:03:57 | 2 с | 1 хв 18 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41930452420), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41930452479) |
| 40 | `e96d701` | [#269](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/269) | 2026-11-04 23:01:33 | 2026-11-04 23:08:08 | 1 хв 32 с | 1 хв 16 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41930843631), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41930843693) |
| 41 | `6129f96` | [#270](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/270) | 2026-11-04 23:03:48 | 2026-11-05 08:28:15 | 2 с | 1 хв 8 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41994553670), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/41994553647) |
| 42 | `01c51fc` | [#272](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/272) | 2026-11-10 16:39:25 | 2026-11-10 21:26:17 | 34 с | 3 хв 44 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42904331257), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42904331120) |
| 43 | `ac9b9bb` | [#274](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/274) | 2026-11-10 17:11:06 | 2026-11-10 21:27:48 | 1 с | 3 хв 51 с | ⚠️ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42904652246), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42904652348); docs cancelled |
| 44 | `cf4b042` | [#275](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/275) | 2026-11-10 20:30:46 | 2026-11-10 21:28:05 | 35 с | 2 хв 23 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42904845363), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42904845530) |
| 45 | `bbd1914` | [#276](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/276) | 2026-11-10 21:19:25 | 2026-11-10 21:30:23 | 2 с | 1 хв 10 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42905492778), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42905492874) |
| 46 | `4307c4c` | [#273](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/273) | 2026-11-10 16:59:00 | 2026-11-10 21:39:42 | 2 с | 1 хв 9 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42907007723), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42907007792) |
| 47 | `15c153c` | [#279](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/279) | 2026-11-10 21:48:40 | 2026-11-10 22:09:08 | 2 с | 1 хв 10 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42911652235), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42911652148) |
| 48 | `f5d7ad7` | [#277](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/277) | 2026-11-10 22:29:33 | 2026-11-10 22:35:36 | 2 с | 1 хв 9 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42915802773), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42915802454) |
| 49 | `f19d3d3` | [#280](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/280) | 2026-11-10 22:29:47 | 2026-11-10 22:37:59 | 2 с | 1 хв 10 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42916167979), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/42916167928) |
| 50 | `f90f675` | [#286](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/286) | 2026-11-11 13:40:52 | 2026-11-11 14:47:51 | 2 с | 1 хв 10 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43041750342), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43041750215) |
| 51 | `f8f70b0` | [#287](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/287) | 2026-11-11 13:53:41 | 2026-11-11 15:28:44 | 4 с | 1 хв 10 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43048546880), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43048545182) |
| 52 | `ba1424e` | [#288](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/288) | 2026-11-11 15:32:29 | 2026-11-11 16:38:53 | 3 с | 2 хв 17 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43060009047), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43060009168) |
| 53 | `07ea577` | [#289](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/289) | 2026-11-11 16:44:29 | 2026-11-11 16:56:37 | 2 с | 2 хв 42 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43062812381), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43062812344) |
| 54 | `ae9455a` | [#290](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/290) | 2026-11-11 16:36:59 | 2026-11-11 17:38:23 | 3 с | 2 хв 37 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43069679712), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43069679594) |
| 55 | `d3b9970` | [#291](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/291) | 2026-11-11 17:02:03 | 2026-11-11 17:56:44 | 2 с | 2 хв 10 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43072652395), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43072652405) |
| 56 | `7a39007` | [#292](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/292) | 2026-11-11 17:58:08 | 2026-11-11 18:11:00 | 18 с | 3 хв 41 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43074658188), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43074658199) |
| 57 | `078c97c` | [#293](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/293) | 2026-11-11 18:05:32 | 2026-11-11 18:16:11 | 2 с | 1 хв 16 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43075923594), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43075923424) |
| 58 | `c30de6a` | [#294](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/294) | 2026-11-11 18:19:50 | 2026-11-11 18:34:16 | 2 с | 2 хв 24 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43078636120), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43078636082) |
| 59 | `1f029bf` | [#295](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/295) | 2026-11-11 18:33:47 | 2026-11-11 19:11:04 | 6 с | 3 хв 5 с | ✅ | [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43084293017), [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43084292970) |
| 60 | `c4e5f2c` | [#296](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/296) | 2026-11-11 20:02:29 | 2026-11-12 16:15:32 | 5 с | 1 хв 27 с | ✅ | [CI](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43256393333), [docs](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43256393369) |

## Перевірена причина серії падінь

30 жовтня `CI` проходив, але `Deploy API docs` падав на кроці `Generate OpenAPI spec`:

```text
ModuleNotFoundError: No module named 'PIL'
```

Робочий процес встановлював лише `fastapi` і `pyyaml`, хоча імпорт застосунку для генерації OpenAPI потребував Pillow та інших залежностей проєкту. Запит на злиття [#231](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/231) замінив вибіркове встановлення на `pip install -r requirements.txt pyyaml`; після цього обидва автоматичні робочі процеси стали зеленими.

## Контрольні підсумки набору даних

| Показник | Значення |
|---|---:|
| Одиниці постачання | 60 |
| Успішні | 48 |
| Із помилкою | 8 |
| Скасовані | 4 |
| Час очікування, медіана / середнє / P75 / максимум | 3 с / 59 с / 29 с / 20 хв 44 с |
| Час виконання, медіана / середнє / P75 / максимум | 1 хв 22 с / 5 хв 28 с / 2 хв 30 с / 1 год 37 хв 57 с |
| Частка в сумарному Lead Time (до CI / черга / виконання) | 95.51% / 0.68% / 3.81% |
| Частка всередині часу CI (черга / виконання) | 15.2% / 84.8% |
| Час проходження зміни, медіана / середнє / P75 | 39 хв 43 с / 2 год 23 хв 41 с / 1 год 27 хв 31 с |

## Правила для DORA-розрахунку

- **Частота розгортань:** усі 60 merge-постачань за 15 календарних днів; окремий робочий процес не є окремим розгортанням.
- **Час проходження зміни:** медіана часу від першого коміту у запиті на злиття до завершення відповідної одиниці для всіх 60 рядків.
- **Частка невдалих змін:** базово `невдалі / усі завершені без скасованих`; додатково показуємо консервативний варіант, де скасовані також вважаються невдалими.
- **Час відновлення після невдалого розгортання:** від завершення першої невдалої одиниці до завершення першої наступної повністю успішної одиниці.
- Скасовані запуски зберігаємо окремо й не маскуємо під успішні.

> ### Нотатка «Використання ШІ»
> - **Інструменти:** Codex (первинне зведення таблиці), Antigravity (валідація через GitHub Actions REST API та експорт доказів `/docs/ci-cd/evidence/`).
> - **Автори та зони відповідальності (за історією Git):** Євгеній Остапенко (Аналітик даних CI/CD — первинний збір запусків `CI` і розрахунок черги/виконання у PR #297; експорт 120 JSON-доказів і розрахунок P75 та часток черги/виконання), Артем Солодкий (розширення таблиці до 60 злитих одиниць у PR #299).
> - **Етап:** збір, валідація і нормалізація історії GitHub Actions для лабораторної роботи №10.
> - **Що згенеровано:** об’єднання парних робочих процесів в одиниці постачання, повна таблиця за період, часові підсумки, зведення часток черги/виконання та опис перевіреної причини падіння.
> - **Що перевірено / відкинуто вручну:** звірено всі 60 одиниць і 120 запусків із GitHub Actions REST API (`Missing: 0`), перевірено SHA, часові мітки, початок і завершення завдань, статуси та посилання GitHub Actions; Dependabot і ручні робочі процеси виключено; різницю змін запиту #231 і збережений JSON у [evidence/main-runs-2026-10-30-to-2026-11-13.json](evidence/main-runs-2026-10-30-to-2026-11-13.json) перевірено окремо.
