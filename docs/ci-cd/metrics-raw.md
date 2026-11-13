# Сирі метрики конвеєра CI/CD (`metrics-raw.md`)

Дані вивантажено з історії GitHub Actions для гілки `main` за останні 2 тижні (50 останніх запусків згідно з командою `gh run list --branch main --limit 50 --json databaseId,headSha,workflowName,conclusion,attempt,createdAt,updatedAt`).
Усі часові мітки наведено в UTC (`ДД.ММ ГГ:ХХ`).

## Таблиця запусків на `main` (50 запусків у хронологічному порядку)

| № | Коміт | PR | Перший коміт PR | Запуск завершено | Черга, хв | Виконання, хв | Статус | Примітка |
|---|---|---|---|---|---:|---:|:---:|---|
| 1 | `89e7904` | #266 | 04.11 22:19 | 04.11 22:30 | 1.9 | 0.7 | ✅ | `Deploy API docs` (run `41925528174`) — Додати докази фінальних метрик SonarCloud |
| 2 | `89e7904` | #266 | 04.11 22:19 | 04.11 22:29 | 0.5 | 1.3 | ✅ | `CI` (run `41925528194`) — Додати докази фінальних метрик SonarCloud |
| 3 | `b6193f0` | #267 | 04.11 22:44 | 04.11 22:52 | 0.5 | 0.7 | ✅ | `Deploy API docs` (run `41928892510`) — Add video link for Lab08 |
| 4 | `b6193f0` | #267 | 04.11 22:44 | 04.11 22:54 | 1.0 | 2.0 | ✅ | `CI` (run `41928892881`) — Add video link for Lab08 |
| 5 | `9834d57` | #268 | 04.11 22:59 | 04.11 23:03 | 0.7 | 0.6 | ✅ | `Deploy API docs` (run `41930452479`) — Docs/lab08 report fix |
| 6 | `9834d57` | #268 | 04.11 22:59 | 04.11 23:03 | 0.0 | 1.2 | ✅ | `CI` (run `41930452420`) — Docs/lab08 report fix |
| 7 | `e96d701` | #269 | 04.11 23:01 | 04.11 23:08 | 1.5 | 1.3 | ✅ | `CI` (run `41930843693`) — docs: add Ostapenko video report link for Lab 8 |
| 8 | `e96d701` | #269 | 04.11 23:01 | 04.11 23:07 | 1.8 | 0.7 | ✅ | `Deploy API docs` (run `41930843631`) — docs: add Ostapenko video report link for Lab 8 |
| 9 | `6129f96` | #270 | 04.11 23:03 | 05.11 08:27 | 0.1 | 0.6 | ✅ | `Deploy API docs` (run `41994553670`) — Rename video_Solonyna to video_Solonyna.txt |
| 10 | `6129f96` | #270 | 04.11 23:03 | 05.11 08:28 | 0.0 | 1.1 | ✅ | `CI` (run `41994553647`) — Rename video_Solonyna to video_Solonyna.txt |
| 11 | `01c51fc` | #272 | 10.11 16:39 | 10.11 21:26 | 3.0 | 1.3 | ✅ | `CI` (run `42904331120`) — docs: record Ostapenko role as Documentation Lead for Lab 9 in TeamCh… |
| 12 | `01c51fc` | #272 | 10.11 16:39 | 10.11 21:23 | 0.6 | 0.7 | ✅ | `Deploy API docs` (run `42904331257`) — docs: record Ostapenko role as Documentation Lead for Lab 9 in TeamCh… |
| 13 | `ac9b9bb` | #274 | 10.11 17:11 | 10.11 21:27 | 2.5 | 1.4 | ✅ | `CI` (run `42904652246`) — fix(reliability): add timeout, guard clauses, and network error handl… |
| 14 | `ac9b9bb` | #274 | 10.11 17:11 | 10.11 21:25 | 0.0 | 1.2 | ⚠️ | `Deploy API docs` (run `42904652348`) — fix(reliability): add timeout, guard clauses, and network error handl… — скасовано concurrency-групою `pages` через новіший коміт у `main` |
| 15 | `cf4b042` | #275 | 10.11 20:30 | 10.11 21:28 | 1.4 | 1.5 | ✅ | `CI` (run `42904845363`) — Frontend redesign |
| 16 | `cf4b042` | #275 | 10.11 20:30 | 10.11 21:26 | 0.6 | 0.7 | ✅ | `Deploy API docs` (run `42904845530`) — Frontend redesign |
| 17 | `bbd1914` | #276 | 10.11 21:19 | 10.11 21:30 | 0.0 | 1.2 | ✅ | `CI` (run `42905492874`) — docs: ADR for seller ratings and in-site user chat |
| 18 | `bbd1914` | #276 | 10.11 21:19 | 10.11 21:29 | 0.1 | 0.6 | ✅ | `Deploy API docs` (run `42905492778`) — docs: ADR for seller ratings and in-site user chat |
| 19 | `4307c4c` | #273 | 10.11 16:59 | 10.11 21:39 | 0.1 | 0.6 | ✅ | `Deploy API docs` (run `42907007723`) — docs(reliability): add resilience scavenger hunt report (Lab 9) |
| 20 | `4307c4c` | #273 | 10.11 16:59 | 10.11 21:39 | 0.0 | 1.1 | ✅ | `CI` (run `42907007792`) — docs(reliability): add resilience scavenger hunt report (Lab 9) |
| 21 | `15c153c` | #279 | 10.11 21:48 | 10.11 22:08 | 0.1 | 0.6 | ✅ | `Deploy API docs` (run `42911652235`) — docs(lab08): update Quality Gate bonus evidence with ruleset and bloc… |
| 22 | `15c153c` | #279 | 10.11 21:48 | 10.11 22:09 | 0.0 | 1.2 | ✅ | `CI` (run `42911652148`) — docs(lab08): update Quality Gate bonus evidence with ruleset and bloc… |
| 23 | `f5d7ad7` | #277 | 10.11 22:29 | 10.11 22:35 | 0.0 | 1.1 | ✅ | `CI` (run `42915802454`) — docs(reliability): add team reliability report for Lab 9 |
| 24 | `f5d7ad7` | #277 | 10.11 22:29 | 10.11 22:35 | 0.1 | 0.6 | ✅ | `Deploy API docs` (run `42915802773`) — docs(reliability): add team reliability report for Lab 9 |
| 25 | `f19d3d3` | #280 | 10.11 22:29 | 10.11 22:37 | 0.0 | 1.2 | ✅ | `CI` (run `42916167979`) — Docs/new features |
| 26 | `f19d3d3` | #280 | 10.11 22:29 | 10.11 22:37 | 0.1 | 0.6 | ✅ | `Deploy API docs` (run `42916167928`) — Docs/new features |
| 27 | `f19d3d3` | #280 | 10.11 22:29 | 11.11 03:08 | 0.1 | 1.9 | ✅ | `Dependabot (pip)` (run `42950538132`) — Docs/new features |
| 28 | `f19d3d3` | #280 | 10.11 22:29 | 11.11 03:07 | 0.1 | 0.4 | ✅ | `Dependabot (GitHub Actions)` (run `42950538137`) — Docs/new features |
| 29 | `f90f675` | #286 | 11.11 13:40 | 11.11 14:47 | 0.0 | 1.2 | ✅ | `CI` (run `43041750215`) — fix(db): connect/pool timeouts and 503 on unavailable database (REL-03) |
| 30 | `f90f675` | #286 | 11.11 13:40 | 11.11 14:47 | 0.1 | 0.6 | ✅ | `Deploy API docs` (run `43041750342`) — fix(db): connect/pool timeouts and 503 on unavailable database (REL-03) |
| 31 | `f8f70b0` | #287 | 11.11 13:53 | 11.11 15:28 | 0.1 | 0.6 | ✅ | `Deploy API docs` (run `43048545182`) — docs(reliability): record Cherniavskyi as Risk Hunter and expand scav… |
| 32 | `f8f70b0` | #287 | 11.11 13:53 | 11.11 15:28 | 0.1 | 1.2 | ✅ | `CI` (run `43048546880`) — docs(reliability): record Cherniavskyi as Risk Hunter and expand scav… |
| 33 | `ba1424e` | #288 | 11.11 15:32 | 11.11 16:38 | 0.1 | 2.3 | ✅ | `CI` (run `43060009047`) — fix(api): narrow image read error handling, 503 on storage failure (REL-02) |
| 34 | `ba1424e` | #288 | 11.11 15:32 | 11.11 16:37 | 0.1 | 0.9 | ✅ | `Deploy API docs` (run `43060009168`) — fix(api): narrow image read error handling, 503 on storage failure (REL-02) |
| 35 | `07ea577` | #289 | 11.11 16:44 | 11.11 16:56 | 1.3 | 1.1 | ✅ | `Deploy API docs` (run `43062812381`) — docs(traceability): map TP-037/TP-038 to FR-006/FR-002 instead of REL-001 |
| 36 | `07ea577` | #289 | 11.11 16:44 | 11.11 16:56 | 0.0 | 2.7 | ✅ | `CI` (run `43062812344`) — docs(traceability): map TP-037/TP-038 to FR-006/FR-002 instead of REL-001 |
| 37 | `ae9455a` | #290 | 11.11 16:36 | 11.11 17:38 | 0.1 | 2.6 | ✅ | `CI` (run `43069679712`) — Lab09/failure analysis healthcheck |
| 38 | `ae9455a` | #290 | 11.11 16:36 | 11.11 17:37 | 0.9 | 1.1 | ✅ | `Deploy API docs` (run `43069679594`) — Lab09/failure analysis healthcheck |
| 39 | `d3b9970` | #291 | 11.11 17:02 | 11.11 17:55 | 0.1 | 0.9 | ✅ | `Deploy API docs` (run `43072652395`) — Add reliability tests to CI as bonus |
| 40 | `d3b9970` | #291 | 11.11 17:02 | 11.11 17:56 | 0.0 | 2.2 | ✅ | `CI` (run `43072652405`) — Add reliability tests to CI as bonus |
| 41 | `7a39007` | #292 | 11.11 17:58 | 11.11 18:11 | 0.3 | 3.7 | ✅ | `CI` (run `43074658199`) — docs(lab09): name reliability engineer and fix REL-03 test name in re… |
| 42 | `7a39007` | #292 | 11.11 17:58 | 11.11 18:08 | 0.8 | 0.7 | ✅ | `Deploy API docs` (run `43074658188`) — docs(lab09): name reliability engineer and fix REL-03 test name in re… |
| 43 | `078c97c` | #293 | 11.11 18:05 | 11.11 18:16 | 0.0 | 1.3 | ✅ | `CI` (run `43075923424`) — docs(lab09): add Ostapenko Loom video link and finalize Lab 9 team roles |
| 44 | `078c97c` | #293 | 11.11 18:05 | 11.11 18:15 | 0.1 | 0.7 | ✅ | `Deploy API docs` (run `43075923594`) — docs(lab09): add Ostapenko Loom video link and finalize Lab 9 team roles |
| 45 | `c30de6a` | #294 | 11.11 18:19 | 11.11 18:34 | 0.0 | 2.4 | ✅ | `CI` (run `43078636120`) — Create video_Solonyna.txt |
| 46 | `c30de6a` | #294 | 11.11 18:19 | 11.11 18:32 | 0.1 | 1.0 | ✅ | `Deploy API docs` (run `43078636082`) — Create video_Solonyna.txt |
| 47 | `1f029bf` | #295 | 11.11 18:33 | 11.11 19:10 | 1.5 | 1.0 | ✅ | `Deploy API docs` (run `43084293017`) — Lab09/loom |
| 48 | `1f029bf` | #295 | 11.11 18:33 | 11.11 19:11 | 0.1 | 3.1 | ✅ | `CI` (run `43084292970`) — Lab09/loom |
| 49 | `c4e5f2c` | #296 | 11.11 20:02 | 12.11 16:15 | 0.3 | 1.2 | ✅ | `CI` (run `43256393333`) — docs(lab09): add Loom video link for Cherniavskyi |
| 50 | `c4e5f2c` | #296 | 11.11 20:02 | 12.11 16:14 | 0.1 | 0.6 | ✅ | `Deploy API docs` (run `43256393369`) — docs(lab09): add Loom video link for Cherniavskyi |

## Підсумкові метрики

Підраховано для всіх 50 запусків (CI, Deploy API docs та Dependabot), окремо для кожного запуску, а не для унікального коміту. Підсумки часу агреговано з хвилин, уже округлених у таблиці.

| Метрика | Значення |
|---|---|
| Успішні | 49 (98%) |
| Невдалі | 0 (0%) |
| Скасовані | 1 (2%) |
| Черга: середнє / медіана / максимум | 0.5 / 0.1 / 3.0 хв |
| Виконання: середнє / медіана / максимум | 1.2 / 1.1 / 3.7 хв |
| Сума часу в черзі / виконання | 23.0 / 61.2 хв |
