import type {
  Category,
  CurrentUser,
  Listing,
  ListingFilters,
  SellerContact,
} from "./types";

const API_ROOT = "/api/v1";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function errorMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          item && typeof item === "object" && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : String(item),
        )
        .join(" · ");
    }
  }
  return fallback;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new ApiError(
      response.status,
      errorMessage(payload, `Помилка запиту (${response.status})`),
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function loginUrl(): string {
  return `${API_ROOT}/auth/login`;
}

export function getCurrentUser(): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/auth/me");
}

export function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}

export function getCategories(): Promise<Category[]> {
  return apiFetch<Category[]>("/categories");
}

export function getListings(filters: ListingFilters): Promise<Listing[]> {
  const params = new URLSearchParams({ limit: "100", sort: filters.sort });
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.categoryId) params.set("category_id", filters.categoryId);
  if (filters.minPrice) params.set("min_price", filters.minPrice);
  if (filters.maxPrice) params.set("max_price", filters.maxPrice);
  return apiFetch<Listing[]>(`/listings?${params.toString()}`);
}

export function getFavorites(): Promise<Listing[]> {
  return apiFetch<Listing[]>("/favorites");
}

export function addFavorite(listingId: string): Promise<void> {
  return apiFetch<void>(`/favorites/${listingId}`, { method: "POST" });
}

export function removeFavorite(listingId: string): Promise<void> {
  return apiFetch<void>(`/favorites/${listingId}`, { method: "DELETE" });
}

export function getSellerContact(listingId: string): Promise<SellerContact> {
  return apiFetch<SellerContact>(`/listings/${listingId}/contact`);
}

export function moderateListing(listingId: string, reason: string): Promise<void> {
  return apiFetch<void>(`/admin/listings/${listingId}/withdraw`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}
