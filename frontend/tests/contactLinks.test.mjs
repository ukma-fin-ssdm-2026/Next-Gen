import assert from "node:assert/strict";
import { test } from "node:test";

import { contactHref, isEmail } from "../src/contactLinks.ts";

// Еталон: початкова реалізація до рефакторингу (Replace Algorithm).
const LEGACY_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

test("contactHref повертає очікувані посилання", () => {
  const cases = [
    ["student@ukma.edu.ua", "mailto:student@ukma.edu.ua"],
    ["  student@ukma.edu.ua  ", "mailto:student@ukma.edu.ua"],
    ["@student_1", "https://t.me/student_1"],
    ["+380 50 123 45 67", "tel:+380501234567"],
    ["(044) 123-45-67", null],
    ["0501234567", "tel:0501234567"],
    ["@ab", null],
    ["просто текст", null],
    ["", null],
  ];
  for (const [input, expected] of cases) {
    assert.equal(contactHref(input), expected, `contactHref(${JSON.stringify(input)})`);
  }
});

test("isEmail поводиться як початковий регулярний вираз на великому наборі рядків", () => {
  const alphabet = ["a", "b", "@", ".", " ", "1", "я"];
  const inputs = [""];
  for (let length = 1; length <= 6; length += 1) {
    const previous = inputs.filter((item) => item.length === length - 1);
    for (const item of previous) for (const char of alphabet) inputs.push(item + char);
  }
  assert.ok(inputs.length > 10000);
  for (const input of inputs) {
    assert.equal(isEmail(input), LEGACY_EMAIL.test(input), JSON.stringify(input));
  }
});

test("isEmail швидко відхиляє патологічний рядок", () => {
  const started = Date.now();
  assert.equal(isEmail(`${"a".repeat(100000)}@${"a".repeat(100000)}`), false);
  assert.equal(isEmail(`${"a".repeat(100000)}@${"a".repeat(100000)}.`), false);
  assert.ok(Date.now() - started < 500);
});
