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
  seller_rating?: SellerRatingSummary;
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

export interface SellerRatingSummary {
  average: number | null;
  count: number;
}

export interface SellerRating extends SellerRatingSummary {
  distribution: Record<string, number> | null;
  my_rating?: number;
}

export type SellerReviewStatus = "VISIBLE" | "HIDDEN";

export interface OwnSellerReview {
  review_id: string;
  seller_id: string;
  listing_id: string | null;
  rating: number;
  status: SellerReviewStatus;
  created_at: string;
  updated_at: string;
}

export interface AdminSellerReview extends OwnSellerReview {
  author_id: string;
  hidden_by: string | null;
  hidden_at: string | null;
  hidden_reason: string | null;
  deleted_at: string | null;
  author_stats: { total_count: number; recent_count: number; recent_one_star_count: number };
}

export interface ChatListingCard {
  listing_id: string;
  available: boolean;
  title: string | null;
  price: number | null;
  image_url: string | null;
}

export interface ChatMessage {
  message_id: string;
  conversation_id: string;
  sender_id: string;
  body: string;
  created_at: string;
  is_own: boolean;
  listing: ChatListingCard | null;
}

export interface ChatParticipant {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
}

export interface ChatConversation {
  conversation_id: string;
  other: ChatParticipant;
  last_message: ChatMessage | null;
  last_message_at: string;
  unread_count: number;
}

export interface ChatConversationPage {
  items: ChatConversation[];
  next_cursor: string | null;
}

export interface ChatMessagePage {
  items: ChatMessage[];
  before_cursor: string | null;
  after_cursor: string | null;
  has_more: boolean;
}

export interface ChatStartResult {
  conversation_id: string;
  message: ChatMessage;
  created: boolean;
}
