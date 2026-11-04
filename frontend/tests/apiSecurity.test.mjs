import assert from "node:assert/strict";
import test from "node:test";

import { approveCategorySuggestion, createCategory, getPublicProfile, updateCategory } from "../src/api.ts";

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

test("category administration uses protected API routes and JSON payloads", async () => {
  globalThis.window = { location: { origin: "https://baraholka-naukma.example" } };
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return new Response(JSON.stringify({
      id: "44444444-4444-4444-4444-444444444444",
      name: "Книги",
      slug: "books",
      description: null,
      is_active: true,
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  };

  await createCategory({ name: "Книги", slug: "books" });
  await updateCategory("44444444-4444-4444-4444-444444444444", { name: "Книжки" });

  assert.equal(calls[0].url.pathname, "/api/v1/categories");
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].init.body), { name: "Книги", slug: "books" });
  assert.equal(calls[1].url.pathname, "/api/v1/categories/44444444-4444-4444-4444-444444444444");
  assert.equal(calls[1].init.method, "PATCH");
  assert.deepEqual(JSON.parse(calls[1].init.body), { name: "Книжки" });
});

test("category suggestion approval can override both name and slug", async () => {
  globalThis.window = { location: { origin: "https://baraholka-naukma.example" } };
  let request;
  globalThis.fetch = async (url, init) => {
    request = { url, init };
    return new Response(JSON.stringify({ status: "APPROVED" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  await approveCategorySuggestion("44444444-4444-4444-4444-444444444444", {
    name: "Музичне обладнання",
    slug: "music-gear",
  });

  assert.equal(request.url.pathname, "/api/v1/category-suggestions/44444444-4444-4444-4444-444444444444/approve");
  assert.deepEqual(JSON.parse(request.init.body), { name: "Музичне обладнання", slug: "music-gear" });
});
