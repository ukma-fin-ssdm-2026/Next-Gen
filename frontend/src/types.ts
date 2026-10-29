export type UserRole = "USER" | "ADMIN";

export interface CurrentUser {
  user_id: string;
  email: string;
  display_name: string;
  role: UserRole;
}

export type ListingCondition = "NEW" | "LIKE_NEW" | "GOOD" | "USED";

export interface ListingImage {
  image_id: string;
  image_url: string;
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
  category_id: string;
  condition: ListingCondition;
  contact: string;
  image_urls: string[];
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
  sort: "newest" | "oldest";
}
