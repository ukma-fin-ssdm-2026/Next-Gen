import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  addFavorite,
  getCategories,
  getCurrentUser,
  getFavorites,
  getListings,
  getSellerContact,
  loginUrl,
  logout,
  moderateListing,
  removeFavorite,
} from "./api";
import type {
  Category,
  CurrentUser,
  Listing,
  ListingCondition,
  ListingFilters,
} from "./types";

const INITIAL_FILTERS: ListingFilters = {
  q: "",
  categoryId: "",
  minPrice: "",
  maxPrice: "",
  sort: "newest",
};

const CONDITION_LABELS: Record<ListingCondition, string> = {
  NEW: "Нове",
  LIKE_NEW: "Як нове",
  GOOD: "Добрий стан",
  USED: "Вживане",
};

function formatPrice(price: number): string {
  return new Intl.NumberFormat("uk-UA", {
    style: "currency",
    currency: "UAH",
    maximumFractionDigits: 0,
  }).format(price);
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Щось пішло не так. Спробуйте ще раз.";
}

function App() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [listings, setListings] = useState<Listing[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [filters, setFilters] = useState<ListingFilters>(INITIAL_FILTERS);
  const [draftFilters, setDraftFilters] = useState<ListingFilters>(INITIAL_FILTERS);
  const [selected, setSelected] = useState<Listing | null>(null);
  const [contact, setContact] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const categoryNames = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories],
  );

  const loadCatalog = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setListings(await getListings(filters));
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void Promise.all([
      getCurrentUser()
        .then(setUser)
        .catch(() => setUser(null))
        .finally(() => setAuthChecked(true)),
      getCategories().then(setCategories).catch(() => setCategories([])),
    ]);
  }, []);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  useEffect(() => {
    if (!user) {
      setFavorites(new Set());
      return;
    }
    void getFavorites()
      .then((items) => setFavorites(new Set(items.map((item) => item.id))))
      .catch(() => setFavorites(new Set()));
  }, [user]);

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    setFilters(draftFilters);
  }

  function clearFilters() {
    setDraftFilters(INITIAL_FILTERS);
    setFilters(INITIAL_FILTERS);
  }

  async function handleLogout() {
    setBusy(true);
    try {
      await logout();
      setUser(null);
      setSelected(null);
      setNotice("Ви вийшли з облікового запису");
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function toggleFavorite(listingId: string) {
    if (!user) {
      window.location.assign(loginUrl());
      return;
    }
    const isFavorite = favorites.has(listingId);
    setBusy(true);
    setError(null);
    try {
      if (isFavorite) await removeFavorite(listingId);
      else await addFavorite(listingId);
      setFavorites((current) => {
        const next = new Set(current);
        if (isFavorite) next.delete(listingId);
        else next.add(listingId);
        return next;
      });
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function revealContact(listingId: string) {
    if (!user) {
      window.location.assign(loginUrl());
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await getSellerContact(listingId);
      setContact(result.contact);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function moderate(listingId: string) {
    const reason = window.prompt("Причина зняття оголошення (5–500 символів):");
    if (!reason) return;
    setBusy(true);
    setError(null);
    try {
      await moderateListing(listingId, reason);
      setSelected(null);
      setNotice("Оголошення знято з публікації");
      await loadCatalog();
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setBusy(false);
    }
  }

  function openListing(listing: Listing) {
    setSelected(listing);
    setContact(null);
    setError(null);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Барахолка НаУКМА — на головну">
          <span className="brand-mark">Б</span>
          <span>
            <strong>Барахолка</strong>
            <small>НаУКМА</small>
          </span>
        </a>
        <nav className="topnav" aria-label="Основна навігація">
          <a href="#catalog">Оголошення</a>
          <a href="#about">Як це працює</a>
        </nav>
        <div className="account-area">
          {authChecked && user ? (
            <>
              <span className="user-chip" title={user.email}>
                <span className="avatar">{user.display_name.slice(0, 1).toUpperCase()}</span>
                <span className="user-copy">
                  <strong>{user.display_name}</strong>
                  <small>{user.role === "ADMIN" ? "Адміністратор" : "Студент"}</small>
                </span>
              </span>
              <button className="button button-ghost compact" disabled={busy} onClick={handleLogout}>
                Вийти
              </button>
            </>
          ) : authChecked ? (
            <a className="button button-primary compact" href={loginUrl()}>
              Увійти через Microsoft
            </a>
          ) : (
            <span className="auth-placeholder" aria-label="Перевіряємо авторизацію" />
          )}
        </div>
      </header>

      <main id="top">
        <section className="hero">
          <div className="hero-copy">
            <span className="eyebrow">Маркетплейс могилянської спільноти</span>
            <h1>Речі знаходять нових власників тут.</h1>
            <p>
              Купуйте й продавайте всередині НаУКМА — без зайвих чатів,
              випадкових людей і загублених оголошень.
            </p>
            <div className="hero-actions">
              <a className="button button-primary" href="#catalog">Переглянути оголошення</a>
              {!user && <a className="button button-light" href={loginUrl()}>Приєднатися</a>}
            </div>
            <div className="trust-row">
              <span>✓ Вхід через НаУКМА</span>
              <span>✓ Контакти лише для студентів</span>
            </div>
          </div>
          <div className="hero-card" aria-hidden="true">
            <div className="hero-orbit orbit-one" />
            <div className="hero-orbit orbit-two" />
            <div className="hero-product">
              <span className="product-icon">⌁</span>
              <strong>Знайшлося!</strong>
              <small>саме те, що треба</small>
            </div>
            <span className="floating-tag tag-one">Книги</span>
            <span className="floating-tag tag-two">Техніка</span>
            <span className="floating-tag tag-three">Одяг</span>
          </div>
        </section>

        <section className="catalog-section" id="catalog">
          <div className="section-heading">
            <div>
              <span className="eyebrow dark">Актуальні пропозиції</span>
              <h2>Оголошення</h2>
            </div>
            <span className="result-count">
              {loading ? "Завантаження…" : `${listings.length} знайдено`}
            </span>
          </div>

          <form className="filters" onSubmit={applyFilters}>
            <label className="search-field">
              <span className="sr-only">Пошук</span>
              <span aria-hidden="true">⌕</span>
              <input
                value={draftFilters.q}
                onChange={(event) => setDraftFilters({ ...draftFilters, q: event.target.value })}
                placeholder="Що шукаєте?"
                minLength={1}
                maxLength={100}
              />
            </label>
            <label>
              <span>Категорія</span>
              <select
                value={draftFilters.categoryId}
                onChange={(event) =>
                  setDraftFilters({ ...draftFilters, categoryId: event.target.value })
                }
              >
                <option value="">Усі категорії</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>{category.name}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Ціна від</span>
              <input
                type="number"
                min="0"
                inputMode="numeric"
                value={draftFilters.minPrice}
                onChange={(event) => setDraftFilters({ ...draftFilters, minPrice: event.target.value })}
                placeholder="0"
              />
            </label>
            <label>
              <span>Ціна до</span>
              <input
                type="number"
                min="0"
                inputMode="numeric"
                value={draftFilters.maxPrice}
                onChange={(event) => setDraftFilters({ ...draftFilters, maxPrice: event.target.value })}
                placeholder="Будь-яка"
              />
            </label>
            <label>
              <span>Сортування</span>
              <select
                value={draftFilters.sort}
                onChange={(event) =>
                  setDraftFilters({
                    ...draftFilters,
                    sort: event.target.value as ListingFilters["sort"],
                  })
                }
              >
                <option value="newest">Спочатку нові</option>
                <option value="oldest">Спочатку старі</option>
              </select>
            </label>
            <button className="button button-primary filter-submit" type="submit">Знайти</button>
            <button className="button button-text" type="button" onClick={clearFilters}>Скинути</button>
          </form>

          {error && <div className="alert alert-error" role="alert">{error}</div>}
          {notice && (
            <div className="alert alert-success" role="status">
              {notice}
              <button onClick={() => setNotice(null)} aria-label="Закрити повідомлення">×</button>
            </div>
          )}

          {loading ? (
            <div className="listing-grid" aria-label="Завантажуємо оголошення">
              {[1, 2, 3, 4].map((item) => <div className="listing-card skeleton" key={item} />)}
            </div>
          ) : listings.length ? (
            <div className="listing-grid">
              {listings.map((listing) => (
                <article className="listing-card" key={listing.id}>
                  <button className="card-main" onClick={() => openListing(listing)}>
                    <ListingImage listing={listing} />
                    <div className="card-body">
                      <div className="card-meta">
                        <span>{categoryNames.get(listing.category_id) ?? "Інше"}</span>
                        <span>{CONDITION_LABELS[listing.condition]}</span>
                      </div>
                      <h3>{listing.title}</h3>
                      <p>{listing.description}</p>
                      <strong className="price">{formatPrice(listing.price)}</strong>
                    </div>
                  </button>
                  <button
                    className={`favorite-button ${favorites.has(listing.id) ? "active" : ""}`}
                    disabled={busy}
                    onClick={() => void toggleFavorite(listing.id)}
                    aria-label={favorites.has(listing.id) ? "Прибрати з обраного" : "Додати в обране"}
                  >
                    {favorites.has(listing.id) ? "♥" : "♡"}
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <span>⌕</span>
              <h3>Нічого не знайшлося</h3>
              <p>Спробуйте змінити фільтри або пошуковий запит.</p>
              <button className="button button-light" onClick={clearFilters}>Очистити фільтри</button>
            </div>
          )}
        </section>

        <section className="how-section" id="about">
          <div>
            <span className="eyebrow dark">Без зайвого клопоту</span>
            <h2>Три кроки до вдалої знахідки</h2>
          </div>
          <div className="steps">
            <article><span>01</span><h3>Знайдіть</h3><p>Скористайтеся пошуком і фільтрами каталогу.</p></article>
            <article><span>02</span><h3>Увійдіть</h3><p>Підтвердьте належність до спільноти через Microsoft.</p></article>
            <article><span>03</span><h3>Домовтеся</h3><p>Отримайте контакт продавця і напишіть напряму.</p></article>
          </div>
        </section>
      </main>

      <footer>
        <div className="brand footer-brand"><span className="brand-mark">Б</span><strong>Барахолка НаУКМА</strong></div>
        <p>Навчальний проєкт SSDM 2026 · Без платежів і доставки всередині сервісу</p>
      </footer>

      {selected && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setSelected(null)}>
          <section
            className="listing-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="listing-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button className="modal-close" onClick={() => setSelected(null)} aria-label="Закрити">×</button>
            <ListingImage listing={selected} large />
            <div className="modal-content">
              <div className="card-meta">
                <span>{categoryNames.get(selected.category_id) ?? "Інше"}</span>
                <span>{CONDITION_LABELS[selected.condition]}</span>
              </div>
              <h2 id="listing-title">{selected.title}</h2>
              <strong className="price modal-price">{formatPrice(selected.price)}</strong>
              <p className="modal-description">{selected.description}</p>
              {contact && <div className="contact-box"><span>Контакт продавця</span><strong>{contact}</strong></div>}
              <div className="modal-actions">
                <button className="button button-primary" disabled={busy} onClick={() => void revealContact(selected.id)}>
                  {user ? "Показати контакт" : "Увійти, щоб побачити контакт"}
                </button>
                <button className="button button-light" disabled={busy} onClick={() => void toggleFavorite(selected.id)}>
                  {favorites.has(selected.id) ? "♥ В обраному" : "♡ Додати в обране"}
                </button>
                {user?.role === "ADMIN" && (
                  <button className="button button-danger" disabled={busy} onClick={() => void moderate(selected.id)}>
                    Зняти з публікації
                  </button>
                )}
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function ListingImage({ listing, large = false }: { listing: Listing; large?: boolean }) {
  const source = [...listing.images].sort((a, b) => a.display_order - b.display_order)[0]?.image_url;
  const [failed, setFailed] = useState(false);

  return (
    <div className={`listing-image ${large ? "large" : ""} ${!source || failed ? "fallback" : ""}`}>
      {source && !failed ? (
        <img src={source} alt="" onError={() => setFailed(true)} />
      ) : (
        <span aria-hidden="true">Б</span>
      )}
    </div>
  );
}

export default App;
