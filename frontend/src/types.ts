export type UserRole = "USER" | "ADMIN";

export interface CurrentUser {
  user_id: string;
  email: string;
  display_name: string;
  role: UserRole;
  avatar_url?: string | null;
  contact?: string | null;
}

export interface PublicProfile {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
}

export type ListingCondition = "NEW" | "LIKE_NEW" | "GOOD" | "USED" | "FOR_PARTS";

export interface ListingImage {
  image_id: string;
  image_url: string;
  thumbnail_url?: string | null;
  display_order: number;
}

export interface Listing {
  id: string;
  title: string;
  description: string;
  price: number;
  category_id: string;
  condition: ListingCondition;
  user_id: string;
  status: string;
  images: ListingImage[];
  created_at: string;
  updated_at: string;
}

export interface ListingWithContact extends Listing {
  contact: string;
  suggested_category_name?: string | null;
}

export interface UploadedImage {
  image_id: string;
  image_url: string;
  thumbnail_url: string;
  display_order: number;
}

export interface ListingCreatePayload {
  title: string;
  description: string;
  price: number;
  category_id?: string;
  suggested_category_name?: string;
  condition: ListingCondition;
  contact: string;
  image_urls: string[];
}

export interface ListingUpdatePayload {
  title?: string;
  description?: string;
  price?: number;
  condition?: ListingCondition;
  contact?: string;
  image_urls?: string[];
}

export type CategorySuggestionStatus = "PENDING" | "APPROVED" | "REJECTED";

export interface CategorySuggestion {
  suggestion_id: string;
  name: string;
  proposer_id: string;
  status: CategorySuggestionStatus;
  reason: string | null;
  category_id: string | null;
  reviewed_by: string | null;
  created_at: string;
  reviewed_at: string | null;
  listings_count: number;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_active: boolean;
}

export interface SellerContact {
  listing_id: string;
  contact: string;
}

export interface ListingFilters {
  q: string;
  categoryId: string;
  minPrice: string;
  maxPrice: string;
  sort: "newest" | "oldest" | "price_asc" | "price_desc";
}

export interface ModerationAction {
  id: string;
  listing_id: string | null;
  target_user_id: string | null;
  moderator_id: string;
  action_type: "WITHDRAW_LISTING" | "BLOCK_USER" | "UNBLOCK_USER";
  reason: string;
  created_at: string;
}

export type ComplaintReason = "SPAM" | "FRAUD" | "PROHIBITED" | "INAPPROPRIATE" | "WRONG_CATEGORY" | "OTHER";
export type ComplaintStatus = "OPEN" | "RESOLVED" | "DISMISSED";

export interface Complaint {
  id: string;
  listing_id: string;
  listing_title: string | null;
  listing_status: string | null;
  reporter_id: string;
  reporter_email: string | null;
  reason: ComplaintReason;
  details: string;
  status: ComplaintStatus;
  created_at: string;
  resolved_at: string | null;
  resolution_note: string;
}

export type FeedbackStatus = "NEW" | "RESOLVED";

export interface FeedbackMessage {
  id: string;
  user_id: string;
  user_email: string | null;
  subject: string;
  message: string;
  status: FeedbackStatus;
  created_at: string;
  resolved_at: string | null;
}

export interface LogEntry {
  id: string;
  created_at: string;
  actor_id: string;
  actor_email: string | null;
  action_type: string;
  listing_id: string | null;
  target_user_id: string | null;
  target_email: string | null;
  details: string;
}

export interface BlockedUser {
  user_id: string;
  email: string;
  display_name: string;
  reason: string | null;
  blocked_at: string | null;
}

export interface BlockedStatus {
  is_blocked: boolean;
  reason: string | null;
  blocked_at: string | null;
}
