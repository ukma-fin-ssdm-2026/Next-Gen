import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Pagination, usePaged } from "./Pagination";
import {
  ApiError,
  deleteSellerReview,
  getAdminReviews,
  getPublicProfile,
  getSellerRating,
  hideSellerReview,
  restoreSellerReview,
  setSellerReview,
} from "./api";
import { formatDateTime } from "./SupportPanels";
import type { AdminSellerReview, SellerRating, SellerRatingSummary } from "./types";
import "./reviews.css";

const ADMIN_PAGE_SIZE = 10;

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Не вдалося виконати запит";
}

function pluralRatings(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return "оцінка";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "оцінки";
  return "оцінок";
}

/** П'ять зірок із частковим заповненням; значення округлюється до десятих. */
export function Stars({ value, size = 18, label }: { value: number; size?: number; label?: string }) {
  const clamped = Math.max(0, Math.min(5, value));
  return (
    <span className="stars" style={{ fontSize: size }} role="img" aria-label={label ?? `${clamped.toFixed(1)} з 5`}>
      <span className="stars-base" aria-hidden="true">★★★★★</span>
      <span className="stars-fill" aria-hidden="true" style={{ width: `${(clamped / 5) * 100}%` }}>★★★★★</span>
    </span>
  );
}

/** Рядок «★★★★☆ 4,6 · 12 оцінок» або підказка, що оцінок поки замало. */
export function RatingSummary({ rating, size = 18 }: { rating: SellerRatingSummary; size?: number }) {
  if (rating.average === null) {
    return (
      <div className="rating-summary rating-muted">
        <Stars value={0} size={size} label="Рейтингу ще немає" />
        <span>
          {rating.count === 0
            ? "Ще немає оцінок"
            : `${rating.count} ${pluralRatings(rating.count)} · рейтинг ще формується`}
        </span>
      </div>
    );
  }
  return (
    <div className="rating-summary">
      <Stars value={rating.average} size={size} />
      <strong>{rating.average.toFixed(1).replace(".", ",")}</strong>
      <span>· {rating.count} {pluralRatings(rating.count)}</span>
    </div>
  );
}

function Distribution({ distribution, total }: { distribution: Record<string, number>; total: number }) {
  return (
    <ul className="rating-distribution" aria-label="Розподіл оцінок">
      {[5, 4, 3, 2, 1].map((score) => {
        const count = distribution[String(score)] ?? 0;
        return (
          <li key={score}>
            <span>{score} ★</span>
            <span className="rating-bar"><span style={{ width: total ? `${(count / total) * 100}%` : "0%" }} /></span>
            <span>{count}</span>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Рейтинг продавця на сторінці оголошення: підсумок і (для не-власника) форма «Ваша оцінка».
 * `fallback` — підсумок із відповіді оголошення; повні дані й власна оцінка підвантажуються окремо.
 */
export function SellerRatingBlock({ sellerId, fallback, canRate, listingId, onError, onNotice }: {
  sellerId: string;
  fallback?: SellerRatingSummary;
  canRate: boolean;
  listingId?: string;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}) {
  const [rating, setRating] = useState<SellerRating | null>(null);
  const [hover, setHover] = useState(0);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setRating(await getSellerRating(sellerId)); } catch { /* підсумок з оголошення лишається */ }
  }, [sellerId]);
  useEffect(() => { setRating(null); void load(); }, [load]);

  async function choose(value: number) {
    setBusy(true);
    try {
      await setSellerReview(sellerId, value, listingId);
      onNotice(rating?.my_rating ? "Оцінку змінено" : "Дякуємо за оцінку");
      await load();
    } catch (requestError) { onError(errorText(requestError)); }
    finally { setBusy(false); }
  }

  async function remove() {
    setBusy(true);
    try { await deleteSellerReview(sellerId); onNotice("Оцінку видалено"); await load(); }
    catch (requestError) { onError(errorText(requestError)); }
    finally { setBusy(false); }
  }

  const summary: SellerRatingSummary = rating ?? fallback ?? { average: null, count: 0 };
  const mine = rating?.my_rating ?? 0;
  const shown = hover || mine;
  return (
    <div className="seller-rating">
      <RatingSummary rating={summary} />
      {rating?.distribution && summary.count > 0 && <Distribution distribution={rating.distribution} total={summary.count} />}
      {canRate && (
        <div className="rate-seller">
          <span className="rate-label">{mine ? `Ваша оцінка: ${mine} з 5` : "Оцініть продавця"}</span>
          <div className="rate-stars" role="radiogroup" aria-label="Ваша оцінка продавця" onMouseLeave={() => setHover(0)}>
            {[1, 2, 3, 4, 5].map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={mine === value}
                aria-label={`${value} з 5`}
                className={value <= shown ? "is-on" : ""}
                disabled={busy}
                onMouseEnter={() => setHover(value)}
                onFocus={() => setHover(value)}
                onBlur={() => setHover(0)}
                onClick={() => void choose(value)}
              >★</button>
            ))}
            {mine > 0 && <button type="button" className="rate-remove" disabled={busy} onClick={() => void remove()}>Видалити</button>}
          </div>
        </div>
      )}
    </div>
  );
}

/** «Мій рейтинг» у профілі: так бачать продавця інші користувачі. */
export function MyRatingCard({ userId }: { userId: string }) {
  const [rating, setRating] = useState<SellerRating | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    setRating(null); setFailed(false);
    getSellerRating(userId).then((item) => { if (!cancelled) setRating(item); }).catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [userId]);
  return (
    <section className="form-block my-rating">
      <div className="form-block-head"><div><h2>Мій рейтинг як продавця</h2><p className="form-hint">Оцінки від покупців. Так бачать вас інші користувачі.</p></div><Link className="button button-light" to={`/sellers/${userId}`}>Мій публічний профіль</Link></div>
      {failed && <p className="form-hint">Не вдалося завантажити рейтинг.</p>}
      {!failed && rating === null && <p className="form-hint">Завантажуємо…</p>}
      {rating && <RatingSummary rating={rating} size={22} />}
      {rating?.distribution && rating.count > 0 && <Distribution distribution={rating.distribution} total={rating.count} />}
    </section>
  );
}

type StatusFilter = "all" | "visible" | "hidden";

function reviewState(review: AdminSellerReview): { label: string; tone: string } {
  if (review.deleted_at) return { label: "Видалена автором", tone: "deleted" };
  if (review.status === "HIDDEN") return { label: "Прихована", tone: "hidden" };
  return { label: "Видима", tone: "visible" };
}

/** Вкладка «Оцінки» в адмін-панелі: усі оцінки, статистика авторів, приховати/відновити. */
export function AdminReviewsPanel({ onError, onNotice }: { onError: (m: string) => void; onNotice: (m: string) => void }) {
  const [items, setItems] = useState<AdminSellerReview[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [query, setQuery] = useState("");
  const [hidingId, setHidingId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setItems(await getAdminReviews(0, 100)); }
    catch (requestError) { setItems([]); onError(errorText(requestError)); }
  }, [onError]);
  useEffect(() => { void load(); }, [load]);

  // Імена авторів і продавців підвантажуємо один раз на користувача.
  useEffect(() => {
    if (!items) return;
    const missing = [...new Set(items.flatMap((item) => [item.author_id, item.seller_id]))].filter((id) => !(id in names));
    if (missing.length === 0) return;
    let cancelled = false;
    void Promise.all(missing.map((id) => getPublicProfile(id).then((profile) => [id, profile.display_name] as const).catch(() => [id, ""] as const)))
      .then((pairs) => { if (!cancelled) setNames((current) => ({ ...current, ...Object.fromEntries(pairs) })); });
    return () => { cancelled = true; };
  }, [items, names]);

  const nameOf = useCallback((id: string) => names[id] || `${id.slice(0, 8)}…`, [names]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("uk");
    return (items ?? []).filter((item) => {
      const state = reviewState(item);
      if (filter === "visible" && state.tone !== "visible") return false;
      if (filter === "hidden" && state.tone === "visible") return false;
      if (!needle) return true;
      return `${nameOf(item.author_id)} ${nameOf(item.seller_id)}`.toLocaleLowerCase("uk").includes(needle);
    });
  }, [items, filter, query, nameOf]);

  const paged = usePaged(filtered, ADMIN_PAGE_SIZE, `${filter}|${query}`);

  async function hide(review: AdminSellerReview) {
    setBusyId(review.review_id);
    try {
      await hideSellerReview(review.review_id, reason.trim());
      onNotice("Оцінку приховано");
      setHidingId(null); setReason("");
      await load();
    } catch (requestError) { onError(errorText(requestError)); }
    finally { setBusyId(null); }
  }

  async function restore(review: AdminSellerReview) {
    setBusyId(review.review_id);
    try { await restoreSellerReview(review.review_id); onNotice("Видимість оцінки відновлено"); await load(); }
    catch (requestError) { onError(errorText(requestError)); }
    finally { setBusyId(null); }
  }

  return (
    <section className="form-block">
      <div className="form-block-head">
        <div><h2>Оцінки продавців</h2><p className="form-hint">Новіші першими. Приховану оцінку не враховано в рейтингу; причину бачать лише адміністратори.</p></div>
        <button className="button button-light" type="button" onClick={() => void load()}>Оновити</button>
      </div>
      <div className="log-toolbar">
        <input type="search" className="log-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Пошук за іменем автора або продавця" aria-label="Пошук оцінок" />
        <select className="log-filter" value={filter} onChange={(event) => setFilter(event.target.value as StatusFilter)} aria-label="Стан оцінки">
          <option value="all">Усі оцінки</option>
          <option value="visible">Видимі</option>
          <option value="hidden">Приховані та видалені</option>
        </select>
      </div>
      {items === null && <p className="form-hint">Завантажуємо…</p>}
      {items !== null && items.length === 0 && <p className="form-hint">Оцінок поки немає.</p>}
      {items !== null && items.length > 0 && <p className="form-hint">Показано {filtered.length} із {items.length}</p>}
      <ul className="review-list">
        {paged.slice.map((review) => {
          const state = reviewState(review);
          const suspicious = review.author_stats.recent_one_star_count >= 3;
          return (
            <li key={review.review_id}>
              <div className="review-head">
                <Stars value={review.rating} size={17} label={`${review.rating} з 5`} />
                <strong><Link className="seller-link" to={`/sellers/${review.seller_id}`}>{nameOf(review.seller_id)}</Link></strong>
                <span className={`status-chip review-${state.tone}`}>{state.label}</span>
              </div>
              <p className="form-hint">
                від {nameOf(review.author_id)} · {formatDateTime(review.created_at)}
                {review.updated_at !== review.created_at && ` · змінено ${formatDateTime(review.updated_at)}`}
                {review.listing_id && <> · <Link to={`/listings/${review.listing_id}`}>оголошення</Link></>}
              </p>
              <p className={`form-hint review-author-stats${suspicious ? " is-warning" : ""}`}>
                Автор: усього {review.author_stats.total_count}, за добу {review.author_stats.recent_count}, з них однозіркових {review.author_stats.recent_one_star_count}
              </p>
              {review.hidden_reason && <p className="log-details">Причина приховування: {review.hidden_reason}{review.hidden_at ? ` (${formatDateTime(review.hidden_at)})` : ""}</p>}
              {hidingId === review.review_id ? (
                <form className="admin-inline" onSubmit={(event) => { event.preventDefault(); void hide(review); }}>
                  <label><span>Причина приховування <small>5–500 символів</small></span><textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={5} maxLength={500} required rows={2} /></label>
                  <div className="form-actions">
                    <button className="button button-danger" type="submit" disabled={busyId === review.review_id || reason.trim().length < 5}>Приховати</button>
                    <button className="button button-text" type="button" onClick={() => { setHidingId(null); setReason(""); }}>Скасувати</button>
                  </div>
                </form>
              ) : (
                <div className="form-actions">
                  {review.status === "VISIBLE" && !review.deleted_at && <button className="button button-light" type="button" disabled={busyId === review.review_id} onClick={() => { setHidingId(review.review_id); setReason(""); }}>Приховати</button>}
                  {review.status === "HIDDEN" && <button className="button button-light" type="button" disabled={busyId === review.review_id} onClick={() => void restore(review)}>Відновити</button>}
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <Pagination page={paged.page} totalPages={paged.totalPages} onChange={paged.setPage} />
    </section>
  );
}
