import assert from "node:assert/strict";
import test from "node:test";

import { sendChatMessage } from "../src/api.ts";

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;
const CONVERSATION = "3FA85F64-5717-4562-B3FC-2C963F66AFA6";
const MESSAGE = "7C9E6679-7425-40DE-944B-E07FC1F90AE7";

test.afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.window = originalWindow;
});

function mockFetch() {
  const calls = [];
  globalThis.window = { location: { origin: "https://baraholka-naukma.example" } };
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
  };
  return calls;
}

test("chat message sends reply_to_id only when replying", async () => {
  const calls = mockFetch();
  await sendChatMessage(CONVERSATION, "Привіт");
  await sendChatMessage(CONVERSATION, "Так", MESSAGE);
  assert.deepEqual(JSON.parse(calls[0].init.body), { body: "Привіт" });
  assert.deepEqual(JSON.parse(calls[1].init.body), { body: "Так", reply_to_id: MESSAGE });
});
