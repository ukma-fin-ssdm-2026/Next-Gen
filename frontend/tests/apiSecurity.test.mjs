import assert from "node:assert/strict";
import test from "node:test";

import { getPublicProfile } from "../src/api.ts";

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;

test.afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.window = originalWindow;
});

test("public profile request stays on the application API origin", async () => {
  globalThis.window = { location: { origin: "https://baraholka-naukma.example" } };
  let requestedUrl;
  globalThis.fetch = async (url) => {
    requestedUrl = url;
    return new Response(JSON.stringify({ user_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  await getPublicProfile("3FA85F64-5717-4562-B3FC-2C963F66AFA6");

  assert.equal(requestedUrl.origin, "https://baraholka-naukma.example");
  assert.equal(requestedUrl.pathname, "/api/v1/users/3fa85f64-5717-4562-b3fc-2c963f66afa6");
});

test("public profile request rejects a server-supplied non-UUID before fetch", async () => {
  globalThis.window = { location: { origin: "https://baraholka-naukma.example" } };
  let fetchCalled = false;
  globalThis.fetch = async () => {
    fetchCalled = true;
    throw new Error("fetch must not be called");
  };

  assert.throws(
    () => getPublicProfile("//attacker.example/profile"),
    /Некоректний ідентифікатор ресурсу/,
  );
  assert.equal(fetchCalled, false);
});
