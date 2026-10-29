import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ApiError,
  addFavorite,
  getCategories,
  getCurrentUser,
  getFavorites,
  getListing,
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

const CATALOG_PAGE_SIZE = 24;

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

function filtersFromParams(params: URLSearchParams): ListingFilters {
  return {
    q: params.get("q") ?? "",
    categoryId: params.get("category") ?? "",
    minPrice: params.get("min_price") ?? "",
    maxPrice: params.get("max_price") ?? "",
    sort: params.get("sort") === "oldest" ? "oldest" : "newest",
  };
}

function paramsFromFilters(filters: ListingFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.categoryId) params.set("category", filters.categoryId);
  if (filters.minPrice) params.set("min_price", filters.minPrice);
  if (filters.maxPrice) params.set("max_price", filters.maxPrice);
  if (filters.sort !== "newest") params.set("sort", filters.sort);
  return params;
}

function useCurrentLoginUrl(): string {
  const location = useLocation();
  return loginUrl(`${location.pathname}${location.search}${location.hash}`);
}

function App() {
  const navigate = useNavigate();
  const currentLoginUrl = useCurrentLoginUrl();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const categoryNames = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories],
  );

  useEffect(() => {
    void Promise.all([
      getCurrentUser()
        .then(setUser)
        .catch(() => setUser(null))
        .finally(() => setAuthChecked(true)),
      getCategories().then(setCategories).catch(() => setCategories([])),
    ]);
  }, []);

  const refreshFavorites = useCallback(async () => {
    if (!user) {
      setFavorites(new Set());
      return;
    }
    try {
      const items = await getFavorites();
      setFavorites(new Set(items.map((item) => item.id)));
    } catch {
      setFavorites(new Set());
    }
  }, [user]);

  useEffect(() => {
    void refreshFavorites();
  }, [refreshFavorites]);

  async function handleLogout() {
    setBusy(true);
    setError(null);
    try {
      await logout();
      setUser(null);
      setFavorites(new Set());
      setNotice("Ви вийшли з облікового запису");
      navigate("/");
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function toggleFavorite(listingId: string) {
    if (!user) {
      window.location.assign(currentLoginUrl);
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

  return (
    <div className="app-shell">
      <Header user={user} authChecked={authChecked} busy={busy} onLogout={() => void handleLogout()} />

      {error && <div className="global-alert-wrap"><div className="alert alert-error" role="alert">{error}</div></div>}
      {notice && (
        <div className="global-alert-wrap">
          <div className="alert alert-success" role="status">
            {notice}
            <button onClick={() => setNotice(null)} aria-label="Закрити повідомлення">×</button>
          </div>
        </div>
      )}

      <Routes>
        <Route
          path="/"
          element={
            <HomePage
              categoryNames={categoryNames}
              user={user}
              favorites={favorites}
              busy={busy}
              onFavorite={(id) => void toggleFavorite(id)}
              onError={setError}
            />
          }
        />
        <Route
          path="/listings"
          element={
            <CatalogPage
              categories={categories}
              categoryNames={categoryNames}
              favorites={favorites}
              busy={busy}
              onFavorite={(id) => void toggleFavorite(id)}
              onError={setError}
            />
          }
        />
        <Route
          path="/listings/:listingId"
          element={
            <ListingPage
              user={user}
              categoryNames={categoryNames}
              favorites={favorites}
              busy={busy}
              onFavorite={(id) => void toggleFavorite(id)}
              onBusy={setBusy}
              onError={setError}
              onNotice={setNotice}
            />
          }
        />
        <Route
          path="/favorites"
          element={
            <FavoritesPage
              user={user}
              authChecked={authChecked}
              categoryNames={categoryNames}
              favorites={favorites}
              busy={busy}
              onFavorite={(id) => void toggleFavorite(id)}
              onError={setError}
            />
          }
        />
        <Route path="/profile" element={<ProfilePage user={user} authChecked={authChecked} />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      <Footer />
    </div>
  );
}

function Header({ user, authChecked, busy, onLogout }: {
  user: CurrentUser | null;
  authChecked: boolean;
  busy: boolean;
  onLogout: () => void;
}) {
  const currentLoginUrl = useCurrentLoginUrl();
  return (
    <header className="topbar">
      <Link className="brand" to="/" aria-label="Барахолка НаУКМА — на головну">
        <span className="brand-mark">Б</span>
        <span><strong>Барахолка</strong><small>НаУКМА</small></span>
      </Link>
      <nav className="topnav" aria-label="Основна навігація">
        <NavLink to="/listings">Оголошення</NavLink>
        {user && <NavLink to="/favorites">Обране</NavLink>}
        {user && <NavLink to="/profile">Профіль</NavLink>}
      </nav>
      <div className="account-area">
        {authChecked && user ? (
          <>
            <Link className="user-chip" to="/profile" title={user.email}>
              <span className="avatar">{user.display_name.slice(0, 1).toUpperCase()}</span>
              <span className="user-copy">
                <strong>{user.display_name}</strong>
                <small>{user.role === "ADMIN" ? "Адміністратор" : "Студент"}</small>
              </span>
            </Link>
            <button className="button button-ghost compact" disabled={busy} onClick={onLogout}>Вийти</button>
          </>
        ) : authChecked ? (
          <a className="button button-primary compact" href={currentLoginUrl}>Увійти через Microsoft</a>
        ) : (
          <span className="auth-placeholder" aria-label="Перевіряємо авторизацію" />
        )}
      </div>
    </header>
  );
}

function HomePage({ categoryNames, user, favorites, busy, onFavorite, onError }: {
  categoryNames: Map<string, string>;
  user: CurrentUser | null;
  favorites: Set<string>;
  busy: boolean;
  onFavorite: (id: string) => void;
  onError: (message: string) => void;
}) {
  const currentLoginUrl = useCurrentLoginUrl();
  const [recentListings, setRecentListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getListings(INITIAL_FILTERS, 4)
      .then(setRecentListings)
      .catch((requestError) => onError(errorText(requestError)))
      .finally(() => setLoading(false));
  }, [onError]);

  return (
    <main>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">Маркетплейс могилянської спільноти</span>
          <h1>Речі знаходять нових власників тут.</h1>
          <p>Купуйте й продавайте всередині НаУКМА — без зайвих чатів, випадкових людей і загублених оголошень.</p>
          <div className="hero-actions">
            <Link className="button button-primary" to="/listings">Переглянути оголошення</Link>
            {!user && <a className="button button-light" href={currentLoginUrl}>Приєднатися</a>}
          </div>
          <div className="trust-row"><span>✓ Вхід через НаУКМА</span><span>✓ Контакти лише для студентів</span></div>
        </div>
        <div className="hero-card" aria-hidden="true">
          <div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" />
          <div className="hero-product"><span className="product-icon">⌁</span><strong>Знайшлося!</strong><small>саме те, що треба</small></div>
          <span className="floating-tag tag-one">Книги</span><span className="floating-tag tag-two">Техніка</span><span className="floating-tag tag-three">Одяг</span>
        </div>
      </section>

      <section className="catalog-section recent-section">
        <div className="section-heading">
          <div><span className="eyebrow dark">Щойно додали</span><h2>Нещодавні оголошення</h2></div>
          <Link className="button button-light" to="/listings">Весь каталог →</Link>
        </div>
        {loading ? <ListingSkeleton /> : recentListings.length ? (
          <ListingGrid listings={recentListings} categoryNames={categoryNames} favorites={favorites} busy={busy} onFavorite={onFavorite} />
        ) : (
          <div className="empty-state"><span>⌁</span><h3>Оголошень поки немає</h3><p>Перші пропозиції з’являться тут.</p></div>
        )}
      </section>

      <section className="how-section">
        <div><span className="eyebrow dark">Без зайвого клопоту</span><h2>Три кроки до вдалої знахідки</h2></div>
        <div className="steps">
          <article><span>01</span><h3>Знайдіть</h3><p>Скористайтеся пошуком і фільтрами каталогу.</p></article>
          <article><span>02</span><h3>Увійдіть</h3><p>Підтвердьте належність до спільноти через Microsoft.</p></article>
          <article><span>03</span><h3>Домовтеся</h3><p>Отримайте контакт продавця і напишіть напряму.</p></article>
        </div>
      </section>
    </main>
  );
}

function CatalogPage({ categories, categoryNames, favorites, busy, onFavorite, onError }: {
  categories: Category[];
  categoryNames: Map<string, string>;
  favorites: Set<string>;
  busy: boolean;
  onFavorite: (id: string) => void;
  onError: (message: string) => void;
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => filtersFromParams(searchParams), [searchParams]);
  const [draftFilters, setDraftFilters] = useState<ListingFilters>(filters);
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const requestGeneration = useRef(0);

  useEffect(() => setDraftFilters(filters), [filters]);
  useEffect(() => {
    const generation = requestGeneration.current + 1;
    requestGeneration.current = generation;
    let cancelled = false;
    setLoading(true);
    setLoadingMore(false);
    getListings(filters, CATALOG_PAGE_SIZE)
      .then((items) => {
        if (cancelled || generation !== requestGeneration.current) return;
        setListings(items);
        setHasMore(items.length === CATALOG_PAGE_SIZE);
      })
      .catch((requestError) => {
        if (!cancelled && generation === requestGeneration.current) {
          onError(errorText(requestError));
        }
      })
      .finally(() => {
        if (!cancelled && generation === requestGeneration.current) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
      if (requestGeneration.current === generation) {
        requestGeneration.current += 1;
      }
    };
  }, [filters, onError]);

  async function loadMore() {
    const generation = requestGeneration.current;
    setLoadingMore(true);
    try {
      const items = await getListings(
        filters,
        CATALOG_PAGE_SIZE,
        listings.length,
      );
      if (generation !== requestGeneration.current) return;
      setListings((current) => [...current, ...items]);
      setHasMore(items.length === CATALOG_PAGE_SIZE);
    } catch (requestError) {
      if (generation === requestGeneration.current) {
        onError(errorText(requestError));
      }
    } finally {
      if (generation === requestGeneration.current) {
        setLoadingMore(false);
      }
    }
  }

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    setSearchParams(paramsFromFilters(draftFilters));
  }

  function clearFilters() {
    setDraftFilters(INITIAL_FILTERS);
    setSearchParams(new URLSearchParams());
  }

  return (
    <main className="page-main catalog-page">
      <section>
        <div className="section-heading">
          <div><span className="eyebrow dark">Весь маркетплейс</span><h1>Оголошення</h1></div>
          <span className="result-count">{loading ? "Завантаження…" : `Показано: ${listings.length}`}</span>
        </div>
        <FilterForm filters={draftFilters} categories={categories} onChange={setDraftFilters} onSubmit={applyFilters} onClear={clearFilters} />
        {loading ? <ListingSkeleton /> : listings.length ? (
          <ListingGrid listings={listings} categoryNames={categoryNames} favorites={favorites} busy={busy} onFavorite={onFavorite} />
        ) : <EmptyState onClear={clearFilters} />}
        {hasMore && !loading && (
          <div className="load-more-row">
            <button
              className="button button-light"
              type="button"
              disabled={loadingMore}
              onClick={() => void loadMore()}
            >
              {loadingMore ? "Завантажуємо…" : "Показати ще"}
            </button>
          </div>
        )}
      </section>
    </main>
  );
}

function FilterForm({ filters, categories, onChange, onSubmit, onClear }: {
  filters: ListingFilters;
  categories: Category[];
  onChange: (filters: ListingFilters) => void;
  onSubmit: (event: FormEvent) => void;
  onClear: () => void;
}) {
  return (
    <form className="filters" onSubmit={onSubmit}>
      <label className="search-field">
        <span className="sr-only">Пошук</span><span aria-hidden="true">⌕</span>
        <input value={filters.q} onChange={(event) => onChange({ ...filters, q: event.target.value })} placeholder="Що шукаєте?" minLength={1} maxLength={100} />
      </label>
      <label><span>Категорія</span><select value={filters.categoryId} onChange={(event) => onChange({ ...filters, categoryId: event.target.value })}>
        <option value="">Усі категорії</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
      </select></label>
      <label><span>Ціна від</span><input type="number" min="0" inputMode="numeric" value={filters.minPrice} onChange={(event) => onChange({ ...filters, minPrice: event.target.value })} placeholder="0" /></label>
      <label><span>Ціна до</span><input type="number" min="0" inputMode="numeric" value={filters.maxPrice} onChange={(event) => onChange({ ...filters, maxPrice: event.target.value })} placeholder="Будь-яка" /></label>
      <label><span>Сортування</span><select value={filters.sort} onChange={(event) => onChange({ ...filters, sort: event.target.value as ListingFilters["sort"] })}>
        <option value="newest">Спочатку нові</option><option value="oldest">Спочатку старі</option>
      </select></label>
      <button className="button button-primary filter-submit" type="submit">Знайти</button>
      <button className="button button-text" type="button" onClick={onClear}>Скинути</button>
    </form>
  );
}

function ListingGrid({ listings, categoryNames, favorites, busy, onFavorite }: {
  listings: Listing[];
  categoryNames: Map<string, string>;
  favorites: Set<string>;
  busy: boolean;
  onFavorite: (id: string) => void;
}) {
  return (
    <div className="listing-grid">
      {listings.map((listing) => (
        <article className="listing-card" key={listing.id}>
          <Link className="card-main" to={`/listings/${listing.id}`}>
            <ListingImage listing={listing} />
            <div className="card-body">
              <div className="card-meta"><span>{categoryNames.get(listing.category_id) ?? "Інше"}</span><span>{CONDITION_LABELS[listing.condition]}</span></div>
              <h3>{listing.title}</h3><p>{listing.description}</p><strong className="price">{formatPrice(listing.price)}</strong>
            </div>
          </Link>
          <button className={`favorite-button ${favorites.has(listing.id) ? "active" : ""}`} disabled={busy} onClick={() => onFavorite(listing.id)} aria-label={favorites.has(listing.id) ? "Прибрати з обраного" : "Додати в обране"}>
            {favorites.has(listing.id) ? "♥" : "♡"}
          </button>
        </article>
      ))}
    </div>
  );
}

function ListingPage({ user, categoryNames, favorites, busy, onFavorite, onBusy, onError, onNotice }: {
  user: CurrentUser | null;
  categoryNames: Map<string, string>;
  favorites: Set<string>;
  busy: boolean;
  onFavorite: (id: string) => void;
  onBusy: (busy: boolean) => void;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}) {
  const { listingId = "" } = useParams();
  const navigate = useNavigate();
  const currentLoginUrl = useCurrentLoginUrl();
  const [listing, setListing] = useState<Listing | null>(null);
  const [contact, setContact] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getListing(listingId).then(setListing).catch((requestError) => onError(errorText(requestError))).finally(() => setLoading(false));
  }, [listingId, onError]);

  async function revealContact() {
    if (!user) { window.location.assign(currentLoginUrl); return; }
    onBusy(true);
    try { setContact((await getSellerContact(listingId)).contact); }
    catch (requestError) { onError(errorText(requestError)); }
    finally { onBusy(false); }
  }

  async function moderate() {
    const reason = window.prompt("Причина зняття оголошення (5–500 символів):");
    if (!reason) return;
    onBusy(true);
    try { await moderateListing(listingId, reason); onNotice("Оголошення знято з публікації"); navigate("/listings"); }
    catch (requestError) { onError(errorText(requestError)); }
    finally { onBusy(false); }
  }

  if (loading) return <PageLoading />;
  if (!listing) return <NotFoundPage />;
  return (
    <main className="page-main listing-detail-page">
      <Link className="back-link" to="/listings">← До оголошень</Link>
      <article className="listing-detail">
        <ListingImage listing={listing} large />
        <div className="listing-detail-content">
          <div className="card-meta"><span>{categoryNames.get(listing.category_id) ?? "Інше"}</span><span>{CONDITION_LABELS[listing.condition]}</span></div>
          <h1>{listing.title}</h1><strong className="price detail-price">{formatPrice(listing.price)}</strong><p className="detail-description">{listing.description}</p>
          {contact && <div className="contact-box"><span>Контакт продавця</span><strong>{contact}</strong></div>}
          <div className="detail-actions">
            <button className="button button-primary" disabled={busy} onClick={() => void revealContact()}>{user ? "Показати контакт" : "Увійти, щоб побачити контакт"}</button>
            <button className="button button-light" disabled={busy} onClick={() => onFavorite(listing.id)}>{favorites.has(listing.id) ? "♥ В обраному" : "♡ Додати в обране"}</button>
            {user?.role === "ADMIN" && <button className="button button-danger" disabled={busy} onClick={() => void moderate()}>Зняти з публікації</button>}
          </div>
        </div>
      </article>
    </main>
  );
}

function FavoritesPage({ user, authChecked, categoryNames, favorites, busy, onFavorite, onError }: {
  user: CurrentUser | null;
  authChecked: boolean;
  categoryNames: Map<string, string>;
  favorites: Set<string>;
  busy: boolean;
  onFavorite: (id: string) => void;
  onError: (message: string) => void;
}) {
  const [items, setItems] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!user) { setItems([]); setLoading(false); return; }
    setLoading(true);
    getFavorites().then(setItems).catch((requestError) => onError(errorText(requestError))).finally(() => setLoading(false));
  }, [user, favorites, onError]);
  if (!authChecked) return <PageLoading />;
  if (!user) return <SignInRequired title="Обране доступне після входу" />;
  return (
    <main className="page-main">
      <PageHeading eyebrow="Ваш особистий список" title="Обране" />
      {loading ? <ListingSkeleton /> : items.length ? (
        <ListingGrid listings={items} categoryNames={categoryNames} favorites={favorites} busy={busy} onFavorite={onFavorite} />
      ) : (
        <div className="empty-state"><span>♡</span><h3>Тут поки порожньо</h3><p>Зберігайте цікаві оголошення, щоб не загубити їх.</p><Link className="button button-primary" to="/listings">Перейти до каталогу</Link></div>
      )}
    </main>
  );
}

function ProfilePage({ user, authChecked }: { user: CurrentUser | null; authChecked: boolean }) {
  if (!authChecked) return <PageLoading />;
  if (!user) return <SignInRequired title="Профіль доступний після входу" />;
  return (
    <main className="page-main narrow-page">
      <PageHeading eyebrow="Ваш обліковий запис" title="Профіль" />
      <section className="profile-card">
        <div className="profile-avatar">{user.display_name.slice(0, 1).toUpperCase()}</div>
        <div><span>Ім’я</span><strong>{user.display_name}</strong></div>
        <div><span>Email НаУКМА</span><strong>{user.email}</strong></div>
        <div><span>Роль</span><strong>{user.role === "ADMIN" ? "Адміністратор" : "Студент"}</strong></div>
      </section>
    </main>
  );
}

function SignInRequired({ title }: { title: string }) {
  const currentLoginUrl = useCurrentLoginUrl();
  return <main className="page-main auth-required"><span className="brand-mark large-mark">Б</span><h1>{title}</h1><p>Увійдіть через корпоративний Microsoft-акаунт НаУКМА.</p><a className="button button-primary" href={currentLoginUrl}>Увійти через Microsoft</a></main>;
}

function PageHeading({ eyebrow, title }: { eyebrow: string; title: string }) {
  return <div className="page-heading"><span className="eyebrow dark">{eyebrow}</span><h1>{title}</h1></div>;
}

function PageLoading() { return <main className="page-main"><ListingSkeleton /></main>; }
function ListingSkeleton() { return <div className="listing-grid" aria-label="Завантажуємо оголошення">{[1, 2, 3, 4].map((item) => <div className="listing-card skeleton" key={item} />)}</div>; }
function EmptyState({ onClear }: { onClear: () => void }) { return <div className="empty-state"><span>⌕</span><h3>Нічого не знайшлося</h3><p>Спробуйте змінити фільтри або пошуковий запит.</p><button className="button button-light" onClick={onClear}>Очистити фільтри</button></div>; }
function NotFoundPage() { return <main className="page-main auth-required"><span className="not-found-code">404</span><h1>Такої сторінки немає</h1><p>Можливо, посилання застаріло або містить помилку.</p><Link className="button button-primary" to="/">Повернутися до каталогу</Link></main>; }

function ListingImage({ listing, large = false }: { listing: Listing; large?: boolean }) {
  const source = [...listing.images].sort((a, b) => a.display_order - b.display_order)[0]?.image_url;
  const [failed, setFailed] = useState(false);
  return <div className={`listing-image ${large ? "large" : ""} ${!source || failed ? "fallback" : ""}`}>{source && !failed ? <img src={source} alt="" onError={() => setFailed(true)} /> : <span aria-hidden="true">Б</span>}</div>;
}

function Footer() {
  return <footer><Link className="brand footer-brand" to="/"><span className="brand-mark">Б</span><strong>Барахолка НаУКМА</strong></Link><p>Навчальний проєкт SSDM 2026 · Без платежів і доставки всередині сервісу</p></footer>;
}

export default App;
