# Бонус 2 — базовий рівень очікування раннера

Дія 5 з плану покращень додає до `CI` групу на номер PR і скасовує застарілий запуск після появи нового коміту. Запуски на `main` і ручні запуски використовують окремі групи за ID запуску.

Метрика для порівняння — медіанний час очікування job `test` у `CI` на `main`: `started_at − created_at` з GitHub Jobs API. У вибірці п'ять найближчих перевірених злиттів із кодом, тестами або конфігурацією до підготовки зміни станом на 18.11.2026. Документаційні злиття й ручні запуски не входять до вибірки. Дати в таблиці наведено в UTC.

| PR | CI на main | Job test | Створено | Почався | Черга |
|---|---|---|---|---|---:|
| [#305](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/305) | [43984806190](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43984806190) | [133710091199](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/43984806190/job/133710091199) | 17.11 00:05:49 | 17.11 00:05:51 | 2 с |
| [#308](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/308) | [44087678634](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44087678634) | [134054282921](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44087678634/job/134054282921) | 17.11 12:55:26 | 17.11 12:55:28 | 2 с |
| [#310](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/310) | [44148711509](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44148711509) | [134270787099](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44148711509/job/134270787099) | 17.11 18:31:10 | 17.11 18:31:12 | 2 с |
| [#311](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/311) | [44151855847](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44151855847) | [134282039393](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44151855847/job/134282039393) | 17.11 18:48:49 | 17.11 18:48:51 | 2 с |
| [#317](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/317) | [44337000738](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44337000738) | [134916305769](https://github.com/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44337000738/job/134916305769) | 18.11 15:33:27 | 18.11 15:33:29 | 2 с |

Медіана та діапазон до зміни становлять **2 с**. У такому тихому зрізі поліпшення медіани може бути непомітним. Після злиття дії 5 потрібно взяти перші п'ять відповідних PR (мінімум три), виключивши саме злиття дії 5. Якщо до злиття дії з'являться нові відповідні запуски, оновити зріз «до». Записати посилання та медіану у [звіт DORA](../dora-summary.md). Додатково звірити кількість PR-запусків із висновком `cancelled`; вони показують, що механізм спрацював. Порівняння черг слід читати з урахуванням навантаження спільних раннерів і вже впровадженого поділу тестів у PR #317.

Джерело міри:

```bash
gh api repos/ukma-fin-ssdm-2026/Next-Gen/actions/runs/44337000738/jobs \
  --jq '.jobs[] | select(.name == "test") | {id, created_at, started_at, html_url}'
```
