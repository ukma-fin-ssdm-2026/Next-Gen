import type {
  BlockedStatus,
  BlockedUser,
  Complaint,
  ComplaintReason,
  ComplaintStatus,
  FeedbackMessage,
  FeedbackStatus,
  LogEntry,
  CategorySuggestion,
  CategorySuggestionStatus,
  Category,
  CurrentUser,
  Listing,
  ListingCreatePayload,
  ListingFilters,
  ListingUpdatePayload,
  ListingWithContact,
  ModerationAction,
  PublicProfile,
  SellerContact,
  UploadedImage,
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

/** Екранує значення, що підставляється в сегмент шляху API (захист від path traversal / SSRF). */
function segment(value: string): string {
  return encodeURIComponent(value);
}

/** Дозволяє лише відносні шляхи API без обходу каталогів і зміни хоста. */
function assertApiPath(path: string): void {
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\") || path.split("?")[0].split("/").some((part) => part === "..")) {
    throw new Error("Некоректний шлях запиту");
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  assertApiPath(path);
  const response = await fetch(`${API_ROOT}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
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

export function loginUrl(returnTo?: string): string {
  const baseUrl = `${API_ROOT}/auth/login`;
  if (!returnTo) return baseUrl;
  return `${baseUrl}?${new URLSearchParams({ next: returnTo }).toString()}`;
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

export function getListings(
  filters: ListingFilters,
  limit = 100,
  skip = 0,
): Promise<Listing[]> {
  // Кожне значення екрануємо encodeURIComponent: фільтри походять з відповідей
  // сервера (id категорій) і введення користувача (q, ціна).
  const pairs: Array<[string, string]> = [
    ["limit", String(limit)],
    ["skip", String(skip)],
    ["sort", filters.sort],
  ];
  if (filters.q.trim()) pairs.push(["q", filters.q.trim()]);
  if (filters.categoryId) pairs.push(["category_id", filters.categoryId]);
  if (filters.minPrice) pairs.push(["min_price", filters.minPrice]);
  if (filters.maxPrice) pairs.push(["max_price", filters.maxPrice]);
  const query = pairs.map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join("&");
  return apiFetch<Listing[]>(`/listings?${query}`);
}

export function getListing(listingId: string): Promise<Listing> {
  return apiFetch<Listing>(`/listings/${segment(listingId)}`);
}

export function uploadListingImages(files: File[]): Promise<UploadedImage[]> {
  const body = new FormData();
  files.forEach((file) => body.append("files", file));
  return apiFetch<UploadedImage[]>("/listings/images", { method: "POST", body });
}

export function createListing(payload: ListingCreatePayload): Promise<ListingWithContact> {
  return apiFetch<ListingWithContact>("/listings", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getMyListings(): Promise<Listing[]> {
  return apiFetch<Listing[]>("/listings/my");
}

export function updateListing(listingId: string, payload: ListingUpdatePayload): Promise<Listing> {
  return apiFetch<Listing>(`/listings/${segment(listingId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteListing(listingId: string): Promise<void> {
  return apiFetch<void>(`/listings/${segment(listingId)}`, { method: "DELETE" });
}

export function getFavorites(): Promise<Listing[]> {
  return apiFetch<Listing[]>("/favorites");
}

export function addFavorite(listingId: string): Promise<void> {
  return apiFetch<void>(`/favorites/${segment(listingId)}`, { method: "POST" });
}

export function removeFavorite(listingId: string): Promise<void> {
  return apiFetch<void>(`/favorites/${segment(listingId)}`, { method: "DELETE" });
}

export function getSellerContact(listingId: string): Promise<SellerContact> {
  return apiFetch<SellerContact>(`/listings/${segment(listingId)}/contact`);
}

export function moderateListing(listingId: string, reason: string): Promise<void> {
  return apiFetch<void>(`/admin/listings/${segment(listingId)}/withdraw`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function updateProfile(payload: { display_name?: string; contact?: string | null }): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/auth/me", { method: "PATCH", body: JSON.stringify(payload) });
}

export function uploadAvatar(file: File): Promise<CurrentUser> {
  const body = new FormData();
  body.append("file", file);
  return apiFetch<CurrentUser>("/auth/me/avatar", { method: "PUT", body });
}

export function deleteAvatar(): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/auth/me/avatar", { method: "DELETE" });
}

export function getPublicProfile(userId: string): Promise<PublicProfile> {
  return apiFetch<PublicProfile>(`/users/${segment(userId)}`);
}

export function blockUser(userId: string, reason: string): Promise<ModerationAction> {
  return apiFetch<ModerationAction>(`/admin/users/${segment(userId)}/block`, { method: "POST", body: JSON.stringify({ reason }) });
}

export function getCategorySuggestions(status: CategorySuggestionStatus = "PENDING"): Promise<CategorySuggestion[]> {
  return apiFetch<CategorySuggestion[]>(`/category-suggestions?status=${encodeURIComponent(status)}`);
}

export function approveCategorySuggestion(suggestionId: string, name?: string): Promise<CategorySuggestion> {
  return apiFetch<CategorySuggestion>(`/category-suggestions/${segment(suggestionId)}/approve`, {
    method: "POST",
    body: JSON.stringify(name ? { name } : {}),
  });
}

export function rejectCategorySuggestion(suggestionId: string, reason: string): Promise<CategorySuggestion> {
  return apiFetch<CategorySuggestion>(`/category-suggestions/${segment(suggestionId)}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function blockUserByEmail(email: string, reason: string): Promise<ModerationAction> {
  return apiFetch<ModerationAction>("/admin/users/block-by-email", { method: "POST", body: JSON.stringify({ email, reason }) });
}

export function unblockUserByEmail(email: string, reason: string): Promise<ModerationAction> {
  return apiFetch<ModerationAction>("/admin/users/unblock-by-email", { method: "POST", body: JSON.stringify({ email, reason }) });
}

export function unblockUser(userId: string, reason: string): Promise<ModerationAction> {
  return apiFetch<ModerationAction>(`/admin/users/${segment(userId)}/unblock`, { method: "POST", body: JSON.stringify({ reason }) });
}

export function getBlockedStatus(): Promise<BlockedStatus> {
  return apiFetch<BlockedStatus>("/auth/blocked-status");
}

export function getBlockedUsers(): Promise<BlockedUser[]> {
  return apiFetch<BlockedUser[]>("/admin/users/blocked");
}

export function submitComplaint(listingId: string, reason: ComplaintReason, details: string): Promise<Complaint> {
  return apiFetch<Complaint>(`/listings/${segment(listingId)}/complaints`, { method: "POST", body: JSON.stringify({ reason, details }) });
}

export function getComplaints(status?: ComplaintStatus): Promise<Complaint[]> {
  return apiFetch<Complaint[]>(`/admin/complaints${status ? `?status=${encodeURIComponent(status)}` : ""}`);
}

export function resolveComplaint(complaintId: string, status: Exclude<ComplaintStatus, "OPEN">, note: string): Promise<Complaint> {
  return apiFetch<Complaint>(`/admin/complaints/${segment(complaintId)}/resolve`, { method: "POST", body: JSON.stringify({ status, note }) });
}

export function submitFeedback(subject: string, message: string): Promise<FeedbackMessage> {
  return apiFetch<FeedbackMessage>("/feedback", { method: "POST", body: JSON.stringify({ subject, message }) });
}

export function getFeedback(status?: FeedbackStatus): Promise<FeedbackMessage[]> {
  return apiFetch<FeedbackMessage[]>(`/admin/feedback${status ? `?status=${encodeURIComponent(status)}` : ""}`);
}

export function resolveFeedback(feedbackId: string): Promise<FeedbackMessage> {
  return apiFetch<FeedbackMessage>(`/admin/feedback/${segment(feedbackId)}/resolve`, { method: "POST" });
}

export function getActivityLog(kind: "users" | "admins", skip = 0, limit = 100): Promise<LogEntry[]> {
  return apiFetch<LogEntry[]>(`/admin/logs/${kind}?skip=${skip}&limit=${limit}`);
}
