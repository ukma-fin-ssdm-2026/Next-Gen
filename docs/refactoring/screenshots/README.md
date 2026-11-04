# Скриншоти для звіту Lab 8

Посилання на зображення вже додані до
`docs/refactoring/sonarcloud-report.md`.

## Додані історичні графіки

- `sonar-history-issues-smells.png` — історія загальної кількості issues та
  Code Smells від початкового стану до нуля.
- `sonar-history-debt-duplicates.png` — історія Technical Debt та кількості
  duplicated lines від початкового стану до нуля.

Точні значення початкового та фінального станів наведено у таблиці звіту.
Вони відповідають аналізам SonarQube Cloud від 2026-10-30 00:01:54 UTC та
2026-11-04 21:22:04 UTC.

## Доданий фінальний стан

### `sonar-after-quality-gate.png`

Скриншот актуальної вкладки `New Code` для `main` після злиття PR
[#263](https://github.com/ukma-fin-ssdm-2026/Next-Gen/pull/263). На кадрі видно:

- Quality Gate — Passed;
- New Issues — 0;
- Security Hotspots — 0;
- Duplications on New Code — 0,17%.

### `sonar-after-overall.png`

Скриншот `Project health dashboard` для `Overall Code`. Він підтверджує:

- Quality Gate — Passed;
- Issues — 0;
- Duplications — 0,2%;
- Security Rating — A;
- Security Issues — 0.

### `sonar-after-security-reliability.png`

Скриншот зрізів Security Hotspot і Reliability для `Overall Code`. Він
підтверджує Security Review Rating A, 0 Security Hotspots, Reliability Rating A
та 0 Reliability Issues.

### `sonar-after-maintainability.png`

Скриншот зрізу Maintainability для `Overall Code`. Він підтверджує
Maintainability Rating A, 0 Maintainability Issues і історичне зменшення
кількості знахідок до нуля.

