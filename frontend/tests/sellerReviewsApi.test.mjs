import assert from "node:assert/strict";
import test from "node:test";

import { deleteSellerReview, getAdminReviews, getSellerListings, getSellerRating, hideSellerReview, setSellerReview } from "../src/api.ts";

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;
const SELLER = "3FA85F64-5717-4562-B3FC-2C963F66AFA6";
const LISTING = "7C9E6679-7425-40DE-944B-E07FC1F90AE7";

test.afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.window = originalWindow;
});

function mockFetch(status = 200, body = {}) {
  const calls = [];
  globalThis.window = { location: { origin: "https://baraholka-naukma.example" } };
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  };
  return calls;
}

test("seller rating and review requests use normalized UUID paths", async () => {
  const calls = mockFetch();
  await getSellerRating(SELLER);
  await setSellerReview(SELLER, 4, LISTING);
  assert.equal(calls[0].url.pathname, "/api/v1/users/3fa85f64-5717-4562-b3fc-2c963f66afa6/rating");
  assert.equal(calls[1].url.pathname, "/api/v1/users/3fa85f64-5717-4562-b3fc-2c963f66afa6/review");
  assert.equal(calls[1].init.method, "PUT");
  assert.deepEqual(JSON.parse(calls[1].init.body), { rating: 4, listing_id: "7c9e6679-7425-40de-944b-e07fc1f90ae7" });
});

test("rating request omits listing context when it is absent", async () => {
  const calls = mockFetch();
  await setSellerReview(SELLER, 5);
  assert.deepEqual(JSON.parse(calls[0].init.body), { rating: 5 });
});

test("own review can be deleted and moderation endpoints are admin-scoped", async () => {
  const calls = mockFetch(204);
  await deleteSellerReview(SELLER);
  assert.equal(calls[0].init.method, "DELETE");
  const admin = mockFetch(200, []);
  await getAdminReviews(0, 100);
  await hideSellerReview(LISTING, "Образливий відгук");
  assert.equal(admin[0].url.pathname, "/api/v1/admin/reviews");
  assert.equal(admin[1].url.pathname, "/api/v1/admin/reviews/7c9e6679-7425-40de-944b-e07fc1f90ae7/hide");
});

test("non-UUID identifiers never reach the network", () => {
  const calls = mockFetch();
  assert.throws(() => getSellerRating("../admin"), /Некоректний ідентифікатор/);
  assert.equal(calls.length, 0);
});

test("seller listings request filters by normalized seller id and reads the total", async () => {
  const calls = mockFetch(200, []);
  const page = await getSellerListings(SELLER, 24, 48);
  assert.equal(calls[0].url.pathname, "/api/v1/listings");
  assert.equal(calls[0].url.searchParams.get("seller_id"), "3fa85f64-5717-4562-b3fc-2c963f66afa6");
  assert.equal(calls[0].url.searchParams.get("skip"), "48");
  assert.deepEqual(page, { items: [], total: 0 });
  await assert.rejects(() => getSellerListings("../x"), /Некоректний ідентифікатор/);
});
