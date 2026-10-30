import { FormEvent, KeyboardEvent as ReactKeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  approveCategorySuggestion,
  blockUser,
  blockUserByEmail,
  createListing,
  deleteListing,
  getCategories,
  getCategorySuggestions,
  getBlockedStatus,
  getCurrentUser,
  getFavorites,
  getListing,
  getListings,
  getMyListings,
  getPublicProfile,
  getSellerContact,
  loginUrl,
  logout,
  moderateListing,
  rejectCategorySuggestion,
  removeFavorite,
  unblockUser,
  unblockUserByEmail,
  deleteAvatar,
  updateListing,
  updateProfile,
  uploadAvatar,
  uploadListingImages,
} from "./api";
import { contactHref } from "./contactLinks";
import { NaukmaLogo } from "./NaukmaLogo";
import {
  ActivityLogPanel,
  BlockedNotice,
  BlockedUsersPanel,
  ComplaintDialog,
  ComplaintsPanel,
  FeedbackAdminPanel,
  FeedbackPage,
} from "./SupportPanels";
import type {
  BlockedStatus,
  Category,
  CategorySuggestion,
  CurrentUser,
  Listing,
  ListingCondition,
  ListingFilters,
  ModerationAction,
  PublicProfile,
} from "./types";

const INITIAL_FILTERS: ListingFilters = {
  q: "",
  categoryId: "",
  minPrice: "",
  maxPrice: "",
  sort: "newest",
};

const CATALOG_PAGE_SIZE = 24;
const STATS_SAMPLE_SIZE = 100;
const MAX_PHOTOS = 10;

const CONDITION_LABELS: Record<ListingCondition, string> = {
  NEW: "Новий",
  LIKE_NEW: "Як новий",
  GOOD: "Задовільний",
  USED: "З помітними дефектами",
  FOR_PARTS: "На запчастини",
};

const MAX_PRICE = 100_000_000;
const SORT_VALUES: ListingFilters["sort"][] = ["newest", "oldest", "price_asc", "price_desc"];

function parseSort(value: string | null): ListingFilters["sort"] {
  return SORT_VALUES.find((item) => item === value) ?? "newest";
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat("uk-UA", {
    style: "currency",
    currency: "UAH",
    maximumFractionDigits: 0,
  }).format(price);
}

function formatAge(iso: string): string {
  const time = Date.parse(iso);
  if (Number.isNaN(time)) return "";
  const minutes = Math.max(0, Math.round((Date.now() - time) / 60000));
  if (minutes < 5) return "щойно";
  if (minutes < 60) return `${minutes} хв тому`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} год тому`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} дн. тому`;
  return new Date(time).toLocaleDateString("uk-UA", { day: "numeric", month: "short" });
}

function freshLabel(count: number): string {
  const lastTwo = count % 100;
  const last = count % 10;
  if (lastTwo >= 11 && lastTwo <= 14) return "нових за добу";
  if (last === 1) return "нове за добу";
  if (last >= 2 && last <= 4) return "нові за добу";
  return "нових за добу";
}

function SearchIcon() {
  return (
    <svg className="search-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" /><path d="m16.2 16.2 4 4" />
    </svg>
  );
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Щось пішло не так. Спробуйте ще раз.";
}

function filtersFromParams(params: URLSearchParams, categories: Category[]): ListingFilters {
  const categoryParam = params.get("category") ?? "";
  const category = categories.find(
    (item) => item.slug === categoryParam || item.id === categoryParam,
  );
  return {
    q: params.get("q") ?? "",
    categoryId: category?.id ?? "",
    minPrice: params.get("min_price") ?? "",
    maxPrice: params.get("max_price") ?? "",
    sort: parseSort(params.get("sort")),
  };
}

function paramsFromFilters(filters: ListingFilters, categories: Category[]): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.categoryId) {
    const category = categories.find((item) => item.id === filters.categoryId);
    params.set("category", category?.slug ?? filters.categoryId);
  }
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
  const [blocked, setBlocked] = useState<BlockedStatus | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const reloadCategories = useCallback(() => {
    getCategories().then((items) => setCategories(sortCategories(items))).catch(() => undefined);
  }, []);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 4000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (!error) return;
    const timer = window.setTimeout(() => setError(null), 4000);
    return () => window.clearTimeout(timer);
  }, [error]);

  const categoryNames = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories],
  );

  useEffect(() => {
    void Promise.all([
      getCurrentUser()
        .then(setUser)
        .catch((requestError) => {
          setUser(null);
          // Заблокований користувач бачить вікно з причиною (FR-013): або сервер
          // повернув 403, або /auth/callback перенаправив сюди з ?blocked=1.
          const redirected = new URLSearchParams(window.location.search).get("blocked") === "1";
          if ((requestError instanceof ApiError && requestError.status === 403) || redirected) {
            return getBlockedStatus()
              .then((status) => setBlocked(status.is_blocked ? status : null))
              .catch(() => undefined);
          }
        })
        .finally(() => setAuthChecked(true)),
      getCategories().then((items) => setCategories(sortCategories(items))).catch(() => setCategories([])),
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
      setBlocked(null);
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
      <Header user={user} authChecked={authChecked} busy={busy} favoritesCount={favorites.size} onLogout={() => void handleLogout()} />
      {blocked && <BlockedNotice status={blocked} busy={busy} onLogout={() => void handleLogout()} />}

      {error && (
        <div className="global-alert-wrap">
          <div className="alert alert-error" role="alert" key={error}>
            <span>{error}</span>
            <button onClick={() => setError(null)} aria-label="Закрити повідомлення">×</button>
          </div>
        </div>
      )}
      {notice && (
        <div className="global-alert-wrap">
          <div className="alert alert-success" role="status" key={notice}>
            <span>{notice}</span>
            <button onClick={() => setNotice(null)} aria-label="Закрити повідомлення">×</button>
          </div>
        </div>
      )}

      <Routes>
        <Route
          path="/"
          element={
            <HomePage
              categories={categories}
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
        <Route path="/listings/new" element={<CreateListingPage user={user} authChecked={authChecked} categories={categories} onError={setError} onNotice={setNotice} />} />
        <Route path="/listings/:listingId/edit" element={<EditListingPage user={user} authChecked={authChecked} categories={categories} onError={setError} onNotice={setNotice} />} />
        <Route path="/my" element={<MyListingsPage user={user} authChecked={authChecked} categoryNames={categoryNames} onError={setError} onNotice={setNotice} />} />
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
        <Route path="/feedback" element={<FeedbackPage user={user} authChecked={authChecked} loginHref={currentLoginUrl} onError={setError} onNotice={setNotice} />} />
        <Route path="/profile" element={<ProfilePage user={user} authChecked={authChecked} onUserChange={setUser} onError={setError} onNotice={setNotice} />} />
        <Route path="/admin/*" element={<AdminPage user={user} authChecked={authChecked} onError={setError} onNotice={setNotice} onCategoriesChanged={reloadCategories} />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      <Footer />
    </div>
  );
}

function HeartIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 20.3s-7.6-4.5-7.6-10.2A4.4 4.4 0 0 1 12 7.4a4.4 4.4 0 0 1 7.6 2.7c0 5.7-7.6 10.2-7.6 10.2Z" />
    </svg>
  );
}

function Avatar({ name, url, className = "" }: { name: string; url?: string | null; className?: string }) {
  return (
    <span className={`avatar ${className}`.trim()} aria-hidden="true">
      {url ? <img src={url} alt="" /> : (name.trim().slice(0, 1) || "?").toUpperCase()}
    </span>
  );
}

function AccountMenu({ user, busy, onLogout }: { user: CurrentUser; busy: boolean; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const location = useLocation();

  useEffect(() => { setOpen(false); }, [location.pathname]);
  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="account-menu" ref={ref}>
      <button className="account-trigger" type="button" aria-haspopup="menu" aria-expanded={open} aria-label="Меню профілю" title={user.email} onClick={() => setOpen((value) => !value)}>
        <Avatar name={user.display_name} url={user.avatar_url} />
        <svg viewBox="0 0 12 8" width="10" height="7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m1 1.5 5 5 5-5" /></svg>
      </button>
      {open && (
        <div className="account-dropdown" role="menu">
          <div className="account-head">
            <strong>{user.display_name}</strong>
            <small>{user.email}</small>
            {user.role === "ADMIN" && <small>Адміністратор</small>}
          </div>
          <Link role="menuitem" to="/my">Мої оголошення</Link>
          <Link role="menuitem" to="/profile">Профіль</Link>
          <Link role="menuitem" to="/feedback">Написати адміністрації</Link>
          {user.role === "ADMIN" && <Link role="menuitem" to="/admin">Адмін-панель</Link>}
          <button role="menuitem" type="button" disabled={busy} onClick={onLogout}>Вийти</button>
        </div>
      )}
    </div>
  );
}

function Header({ user, authChecked, busy, favoritesCount, onLogout }: {
  user: CurrentUser | null;
  authChecked: boolean;
  busy: boolean;
  favoritesCount: number;
  onLogout: () => void;
}) {
  const currentLoginUrl = useCurrentLoginUrl();
  const createLoginUrl = loginUrl("/listings/new");
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [hidden, setHidden] = useState(false);
  const onFormPage = /^\/(listings\/new|listings\/[^/]+\/edit|profile)\/?$/.test(location.pathname);
  const closeMenu = useCallback(() => setMenuOpen(false), []);

  useEffect(() => { setMenuOpen(false); setHidden(false); }, [location.pathname]);
  useEffect(() => {
    let lastY = window.scrollY;
    let ticking = false;
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(() => {
        const y = window.scrollY;
        const delta = y - lastY;
        if (y < 90) setHidden(false);
        else if (delta > 6) setHidden(true);
        else if (delta < -6) setHidden(false);
        if (Math.abs(delta) > 6 || y < 90) lastY = y;
        ticking = false;
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setMenuOpen(false); };
    document.addEventListener("keydown", onKey);
    document.body.classList.add("menu-open");
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("menu-open");
    };
  }, [menuOpen]);

  const favoritesLabel = favoritesCount > 0 ? `Обране, збережено: ${favoritesCount}` : "Обране";
  const onCreatePage = location.pathname === "/listings/new";

  return (
    <>
      <header className={`topbar${hidden && !menuOpen ? " topbar-hidden" : ""}`} onFocusCapture={() => setHidden(false)}>
        <Link className="brand" to="/" aria-label="Барахолка НаУКМА, на головну">
          <span className="brand-mark">Б</span>
          <span><strong>Барахолка</strong><small>НаУКМА</small></span>
        </Link>
        <div className="header-actions">
          <nav className="topnav" aria-label="Основна навігація">
            <NavLink to="/listings" end>Оголошення</NavLink>
          </nav>
          {authChecked && user && (
            <NavLink className="icon-button fav-button" to="/favorites" aria-label={favoritesLabel} title="Обране">
              <HeartIcon />
              {favoritesCount > 0 && <span className="badge" aria-hidden="true">{favoritesCount > 99 ? "99+" : favoritesCount}</span>}
            </NavLink>
          )}
          {user ? (
            <Link className="button button-primary create-button" to="/listings/new" aria-label="Створити оголошення"><span aria-hidden="true">+</span> Створити</Link>
          ) : (
            <a className="button button-primary create-button" href={createLoginUrl} aria-label="Створити оголошення"><span aria-hidden="true">+</span> Створити</a>
          )}
          {authChecked && user ? (
            <AccountMenu user={user} busy={busy} onLogout={onLogout} />
          ) : authChecked ? (
            <a className="button button-ghost compact login-button" href={currentLoginUrl}>Увійти</a>
          ) : (
            <span className="auth-placeholder" aria-label="Перевіряємо авторизацію" />
          )}
        </div>
        <button
          className="burger"
          type="button"
          aria-label={menuOpen ? "Закрити меню" : "Відкрити меню"}
          aria-expanded={menuOpen}
          aria-controls="mobile-menu"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span /><span /><span />
        </button>
      </header>

      {!onCreatePage && (
        user ? (
          <Link className={`fab${hidden || menuOpen || onFormPage ? " fab-hidden" : ""}`} to="/listings/new" aria-label="Створити оголошення">+</Link>
        ) : (
          <a className={`fab${hidden || menuOpen || onFormPage ? " fab-hidden" : ""}`} href={createLoginUrl} aria-label="Створити оголошення">+</a>
        )
      )}

      {menuOpen && <div className="menu-backdrop" onClick={closeMenu} aria-hidden="true" />}
      <aside id="mobile-menu" className={`mobile-menu${menuOpen ? " open" : ""}`} aria-label="Меню">
        <div className="drawer-head">
          <span className="eyebrow dark">Меню</span>
          <button className="drawer-close" type="button" aria-label="Закрити меню" onClick={closeMenu}>×</button>
        </div>
        {authChecked && user && (
          <Link className="drawer-user" to="/profile">
            <Avatar name={user.display_name} url={user.avatar_url} />
            <span><strong>{user.display_name}</strong><small>{user.email}</small></span>
          </Link>
        )}
        <nav className="drawer-nav" aria-label="Мобільна навігація">
          <NavLink to="/" end>Головна</NavLink>
          <NavLink to="/listings" end>Оголошення</NavLink>
          <NavLink to="/listings/new">Створити оголошення</NavLink>
          {user && <NavLink to="/my">Мої оголошення</NavLink>}
          {user && <NavLink to="/favorites">Обране{favoritesCount > 0 ? ` (${favoritesCount})` : ""}</NavLink>}
          {user && <NavLink to="/profile">Профіль</NavLink>}
          {user?.role === "ADMIN" && <NavLink to="/admin">Адмін-панель</NavLink>}
        </nav>
        <div className="drawer-foot">
          {authChecked && user ? (
            <button className="button button-light" disabled={busy} onClick={() => { closeMenu(); onLogout(); }}>Вийти</button>
          ) : authChecked ? (
            <a className="button button-primary" href={currentLoginUrl}>Увійти через Microsoft</a>
          ) : null}
        </div>
      </aside>
    </>
  );
}

const STATUS_LABELS: Record<string, string> = {
  ACTIVE: "Активне",
  RESERVED: "Зарезервоване",
  SOLD: "Продане",
  WITHDRAWN: "Знято",
  REMOVED_BY_MODERATOR: "Знято модератором",
};

const PHONE_PREFIX = "Тел.: ";
const LOCATION_PREFIX = "Локація: ";
const PHONE_PATTERN = /^\+?[0-9][0-9\s()-]{6,19}$/;

// Бекенд зберігає один рядок contact (до 200 символів), тому телефон і локацію
// пакуємо в нього окремими рядками; старі односкладові контакти читаються як є.
function packContact(parts: { main: string; phone: string; location: string }): string {
  return [
    parts.main.trim(),
    parts.phone.trim() ? `${PHONE_PREFIX}${parts.phone.trim()}` : "",
    parts.location.trim() ? `${LOCATION_PREFIX}${parts.location.trim()}` : "",
  ].filter(Boolean).join("\n");
}

function unpackContact(raw: string): { main: string; phone: string; location: string } {
  const result = { main: "", phone: "", location: "" };
  const rest: string[] = [];
  raw.split("\n").forEach((line) => {
    const value = line.trim();
    if (value.startsWith(PHONE_PREFIX)) result.phone = value.slice(PHONE_PREFIX.length).trim();
    else if (value.startsWith(LOCATION_PREFIX)) result.location = value.slice(LOCATION_PREFIX.length).trim();
    else if (value) rest.push(value);
  });
  result.main = rest.join(" ");
  return result;
}

type PhotoItem = { id: string; preview: string; url?: string; file?: File; original?: File };

const CROP_ASPECT = 4 / 3;
const CROP_OUTPUT_WIDTH = 1600;

type CropJob = { id: string; kind: "new"; file: File } | { id: string; kind: "edit"; photoId: string; src: string; name: string; revoke: boolean };

type CropFill = "blur" | "light" | "dark";

const GAP_COLORS: Record<Exclude<CropFill, "blur">, string> = { light: "#ffffff", dark: "#101814" };
const BLUR_SAMPLE = { w: 32, h: 24 };

/** Малює фон полів навколо фото: розмита копія або однотонна заливка. */
function paintGaps(
  context: CanvasRenderingContext2D,
  image: HTMLImageElement,
  natural: { w: number; h: number },
  fill: CropFill,
  outW: number,
  outH: number,
) {
  if (fill !== "blur") {
    context.fillStyle = GAP_COLORS[fill];
    context.fillRect(0, 0, outW, outH);
    return;
  }
  const tiny = document.createElement("canvas");
  tiny.width = BLUR_SAMPLE.w;
  tiny.height = BLUR_SAMPLE.h;
  const tinyContext = tiny.getContext("2d");
  if (!tinyContext) return;
  const cover = Math.max(BLUR_SAMPLE.w / natural.w, BLUR_SAMPLE.h / natural.h);
  tinyContext.drawImage(image, (BLUR_SAMPLE.w - natural.w * cover) / 2, (BLUR_SAMPLE.h - natural.h * cover) / 2, natural.w * cover, natural.h * cover);
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.drawImage(tiny, 0, 0, outW, outH);
  context.fillStyle = "rgba(255, 255, 255, 0.18)";
  context.fillRect(0, 0, outW, outH);
}

function PhotoCropper({ src, name, queued, aspect = CROP_ASPECT, outputWidth = CROP_OUTPUT_WIDTH, title = "Обріжте фото", hint, onCancel, onSkip, onDone, onUnreadable }: {
  src: string;
  name: string;
  queued: number;
  aspect?: number;
  outputWidth?: number;
  title?: string;
  hint?: string;
  onCancel: () => void;
  onSkip: () => void;
  onDone: (blob: Blob) => void;
  onUnreadable: () => void;
}) {
  const frameRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  const [frame, setFrame] = useState({ w: 0, h: 0 });
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [fill, setFill] = useState<CropFill>("blur");
  const imageRef = useRef<HTMLImageElement | null>(null);

  const minScale = natural && frame.w ? Math.max(frame.w / natural.w, frame.h / natural.h) : 1;
  const fitRatio = natural && frame.w ? Math.min(frame.w / natural.w, frame.h / natural.h) / minScale : 1;
  const scale = minScale * zoom;
  const hasGaps = Boolean(natural) && (natural!.w * scale < frame.w - 1 || natural!.h * scale < frame.h - 1);

  const clamp = useCallback((x: number, y: number, nextScale: number) => {
    if (!natural) return { x: 0, y: 0 };
    const gapX = frame.w - natural.w * nextScale;
    const gapY = frame.h - natural.h * nextScale;
    return {
      x: Math.min(Math.max(0, gapX), Math.max(Math.min(0, gapX), x)),
      y: Math.min(Math.max(0, gapY), Math.max(Math.min(0, gapY), y)),
    };
  }, [natural, frame.w, frame.h]);

  useEffect(() => {
    const measure = () => {
      const node = frameRef.current;
      if (node) setFrame({ w: node.clientWidth, h: node.clientHeight });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  useEffect(() => {
    if (!natural || !frame.w) return;
    const base = Math.max(frame.w / natural.w, frame.h / natural.h);
    setZoom(1);
    setOffset({ x: (frame.w - natural.w * base) / 2, y: (frame.h - natural.h * base) / 2 });
  }, [natural, frame.w, frame.h]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onCancel(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);

  const changeZoom = (next: number) => {
    const value = Math.min(4, Math.max(fitRatio, next));
    if (!natural) return;
    const nextScale = minScale * value;
    const cx = (frame.w / 2 - offset.x) / scale;
    const cy = (frame.h / 2 - offset.y) / scale;
    setZoom(value);
    setOffset(clamp(frame.w / 2 - cx * nextScale, frame.h / 2 - cy * nextScale, nextScale));
  };

  const confirm = () => {
    const image = imageRef.current;
    if (!image || !natural) return;
    const outW = Math.round(Math.min(outputWidth, frame.w / scale));
    const outH = Math.round(outW / aspect);
    const k = outW / frame.w;
    const canvas = document.createElement("canvas");
    canvas.width = outW;
    canvas.height = outH;
    const context = canvas.getContext("2d");
    if (!context) { onSkip(); return; }
    if (hasGaps) paintGaps(context, image, natural, fill, outW, outH);
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    context.drawImage(image, offset.x * k, offset.y * k, natural.w * scale * k, natural.h * scale * k);
    canvas.toBlob((blob) => { if (blob) onDone(blob); else onSkip(); }, "image/jpeg", 0.92);
  };

  return (
    <div className="crop-overlay" role="dialog" aria-modal="true" aria-label="Обрізання фото" onMouseDown={(event) => { if (event.target === event.currentTarget) onCancel(); }}>
      <div className="crop-dialog">
        <div className="crop-head">
          <h2>{title}</h2>
          <p>{hint ?? "Кадр 4:3 такий самий, як у каталозі й на сторінці оголошення. Можна заповнити його фото або вписати фото повністю, а порожні місця заповнити полями."}{queued > 0 ? ` Ще фото в черзі: ${queued}.` : ""}</p>
        </div>
        <div
          className={`crop-frame${aspect === 1 ? " crop-frame-square" : ""}`}
          style={{ aspectRatio: String(aspect) }}
          ref={frameRef}
          tabIndex={0}
          onPointerDown={(event) => { event.currentTarget.setPointerCapture(event.pointerId); dragRef.current = { x: event.clientX, y: event.clientY, ox: offset.x, oy: offset.y }; }}
          onPointerMove={(event) => { const drag = dragRef.current; if (drag) setOffset(clamp(drag.ox + event.clientX - drag.x, drag.oy + event.clientY - drag.y, scale)); }}
          onPointerUp={() => { dragRef.current = null; }}
          onPointerCancel={() => { dragRef.current = null; }}
          onWheel={(event) => changeZoom(zoom - event.deltaY * 0.0025)}
          onKeyDown={(event) => {
            const step = 24;
            const moves: Record<string, [number, number]> = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
            const move = moves[event.key];
            if (move) { event.preventDefault(); setOffset((current) => clamp(current.x + move[0], current.y + move[1], scale)); }
          }}
        >
          {hasGaps && (fill === "blur"
            ? <img className="crop-backdrop" src={src} alt="" draggable={false} aria-hidden="true" />
            : <span className="crop-solid" style={{ background: fill === "light" ? "#ffffff" : "#101814" }} aria-hidden="true" />)}
          <img
            ref={imageRef}
            src={src}
            alt={name}
            draggable={false}
            onLoad={(event) => setNatural({ w: event.currentTarget.naturalWidth, h: event.currentTarget.naturalHeight })}
            onError={onUnreadable}
            style={natural ? { width: natural.w * scale, height: natural.h * scale, transform: `translate(${offset.x}px, ${offset.y}px)` } : { visibility: "hidden" }}
          />
          <span className="crop-grid" aria-hidden="true" />
        </div>
        <div className="crop-modes" role="group" aria-label="Режим кадру">
          <button type="button" className={!hasGaps ? "active" : ""} onClick={() => { if (!natural) return; setZoom(1); setOffset({ x: (frame.w - natural.w * minScale) / 2, y: (frame.h - natural.h * minScale) / 2 }); }}>Заповнити кадр</button>
          <button type="button" className={hasGaps ? "active" : ""} disabled={fitRatio > 0.995} onClick={() => { if (!natural) return; const nextScale = minScale * fitRatio; setZoom(fitRatio); setOffset({ x: (frame.w - natural.w * nextScale) / 2, y: (frame.h - natural.h * nextScale) / 2 }); }}>Вписати повністю</button>
        </div>
        <label className="crop-zoom">
          <span>Масштаб</span>
          <input type="range" min={fitRatio} max="4" step="0.01" value={zoom} onChange={(event) => changeZoom(Number(event.target.value))} />
        </label>
        {hasGaps && (
          <div className="crop-fill" role="group" aria-label="Чим заповнити поля">
            <span>Поля</span>
            <button type="button" className={fill === "blur" ? "active" : ""} onClick={() => setFill("blur")}>Розмиття</button>
            <button type="button" className={fill === "light" ? "active" : ""} onClick={() => setFill("light")}>Світлі</button>
            <button type="button" className={fill === "dark" ? "active" : ""} onClick={() => setFill("dark")}>Темні</button>
          </div>
        )}
        <div className="crop-actions">
          <button className="button button-text" type="button" onClick={onCancel}>Скасувати</button>
          <button className="button button-primary" type="button" disabled={!natural} onClick={confirm}>Готово</button>
        </div>
      </div>
    </div>
  );
}


function ListingForm({ mode, listing, initialContact, categories, onError, onNotice }: {
  mode: "create" | "edit";
  listing?: Listing;
  initialContact?: string;
  categories: Category[];
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}) {
  const navigate = useNavigate();
  const editing = mode === "edit";
  const [title, setTitle] = useState(listing?.title ?? "");
  const [categoryId, setCategoryId] = useState(listing?.category_id ?? "");
  const [suggestedName, setSuggestedName] = useState("");
  const [price, setPrice] = useState(listing ? String(listing.price) : "");
  const [condition, setCondition] = useState<ListingCondition>(listing?.condition ?? "GOOD");
  const [description, setDescription] = useState(listing?.description ?? "");
  const initialParts = useMemo(() => unpackContact(initialContact ?? ""), [initialContact]);
  const [contact, setContact] = useState(initialParts.main);
  const [phone, setPhone] = useState(initialParts.phone);
  const [location, setLocation] = useState(initialParts.location);
  const [photos, setPhotos] = useState<PhotoItem[]>(() =>
    [...(listing?.images ?? [])]
      .sort((a, b) => a.display_order - b.display_order)
      .map((image) => ({ id: image.image_id, preview: image.thumbnail_url || image.image_url, url: image.image_url })),
  );
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const photosRef = useRef(photos);
  photosRef.current = photos;
  const [cropQueue, setCropQueue] = useState<CropJob[]>([]);
  const cropJob = cropQueue[0] ?? null;
  const cropSource = useMemo(() => {
    if (!cropJob) return null;
    if (cropJob.kind === "new") return { src: URL.createObjectURL(cropJob.file), name: cropJob.file.name, revoke: true };
    return { src: cropJob.src, name: cropJob.name, revoke: cropJob.revoke };
  }, [cropJob]);
  useEffect(() => () => { if (cropSource?.revoke) URL.revokeObjectURL(cropSource.src); }, [cropSource]);

  useEffect(() => () => photosRef.current.forEach((photo) => { if (photo.file) URL.revokeObjectURL(photo.preview); }), []);

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const room = Math.max(MAX_PHOTOS - photos.length, 0);
    const files = Array.from(list).slice(0, room);
    setFormError(list.length > room ? `Можна додати не більше ${MAX_PHOTOS} фото` : null);
    setCropQueue((current) => [...current, ...files.map((file, position) => ({ id: `${Date.now()}-${position}-${file.name}`, kind: "new" as const, file }))]);
  };

  const finishCrop = (blob: Blob | null) => {
    if (!cropJob) return;
    if (blob) {
      const baseName = (cropJob.kind === "new" ? cropJob.file.name : cropJob.name).replace(/\.[^.]+$/, "") || "photo";
      const cropped = new File([blob], `${baseName}.jpg`, { type: "image/jpeg" });
      const preview = URL.createObjectURL(cropped);
      if (cropJob.kind === "new") {
        setPhotos((current) => [...current, { id: preview, preview, file: cropped, original: cropJob.file }]);
      } else {
        setPhotos((current) => current.map((photo) => {
          if (photo.id !== cropJob.photoId) return photo;
          if (photo.file) URL.revokeObjectURL(photo.preview);
          return { id: preview, preview, file: cropped, original: photo.original ?? photo.file };
        }));
      }
    } else if (cropJob.kind === "new") {
      const file = cropJob.file;
      const preview = URL.createObjectURL(file);
      setPhotos((current) => [...current, { id: preview, preview, file }]);
    }
    setCropQueue((current) => current.slice(1));
  };

  const startRecrop = (photo: PhotoItem) => {
    const original = photo.original ?? photo.file;
    const src = original ? URL.createObjectURL(original) : photo.url ?? photo.preview;
    setCropQueue((current) => [...current, { id: `edit-${photo.id}`, kind: "edit", photoId: photo.id, src, name: original?.name ?? "photo", revoke: Boolean(original) }]);
  };

  const removePhoto = (index: number) => {
    setPhotos((current) => {
      if (current[index].file) URL.revokeObjectURL(current[index].preview);
      return current.filter((_, position) => position !== index);
    });
  };

  const makeCover = (index: number) => {
    setPhotos((current) => [current[index], ...current.filter((_, position) => position !== index)]);
  };

  const isOtherCategory = !editing && categoryId === OTHER_CATEGORY_ID;
  const suggestion = isOtherCategory ? suggestedName.trim() : "";
  const isNewCategory = suggestion.length > 0;

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);
    if (isNewCategory) {
      if (suggestion.length < SUGGESTION_MIN || suggestion.length > SUGGESTION_MAX) {
        setFormError(`Назва категорії: від ${SUGGESTION_MIN} до ${SUGGESTION_MAX} символів`);
        return;
      }
    }
    if (photos.length === 0) {
      setFormError("Додайте щонайменше одне фото");
      return;
    }
    if (phone.trim() && !PHONE_PATTERN.test(phone.trim())) {
      setFormError("Перевірте номер телефону: лише цифри, пробіли, дужки й дефіс, можна з «+» на початку");
      return;
    }
    const packedContact = packContact({ main: contact, phone, location });
    if (packedContact.length > 200) {
      setFormError("Контактні дані задовгі, скоротіть їх");
      return;
    }
    setSubmitting(true);
    try {
      const newFiles = photos.filter((photo) => photo.file).map((photo) => photo.file as File);
      const uploaded = newFiles.length > 0
        ? [...(await uploadListingImages(newFiles))].sort((a, b) => a.display_order - b.display_order)
        : [];
      let next = 0;
      const imageUrls = photos.map((photo) => photo.url ?? uploaded[next++].image_url);
      if (editing && listing) {
        await updateListing(listing.id, {
          title: title.trim(),
          description: description.trim(),
          price: Number(price),
          condition,
          image_urls: imageUrls,
          ...(initialContact || contact.trim() ? { contact: packedContact } : {}),
        });
        onNotice("Зміни збережено");
        navigate(`/listings/${listing.id}`);
      } else {
        const created = await createListing({
          title: title.trim(),
          description: description.trim(),
          price: Number(price),
          ...(isNewCategory ? { suggested_category_name: suggestion } : { category_id: categoryId }),
          condition,
          contact: packedContact,
          image_urls: imageUrls,
        });
        onNotice(isNewCategory ? `Оголошення опубліковано в «Інше». Категорію «${suggestion}» розгляне адміністратор` : "Оголошення опубліковано");
        navigate(`/listings/${created.id}`);
      }
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Не вдалося зберегти оголошення";
      setFormError(message);
      onError(message);
      setSubmitting(false);
    }
  };

  const backTo = editing && listing ? `/listings/${listing.id}` : "/listings";
  return (
    <main className="page-main create-page">
      {cropJob && cropSource && (
        <PhotoCropper
          key={cropJob.id}
          src={cropSource.src}
          name={cropSource.name}
          queued={cropQueue.length - 1}
          onCancel={() => setCropQueue((current) => current.slice(1))}
          onSkip={() => finishCrop(null)}
          onDone={(blob) => finishCrop(blob)}
          onUnreadable={() => { setFormError("Це фото не вдалося відкрити для обрізання, його додано без змін."); finishCrop(null); }}
        />
      )}
      <Link className="back-link" to={backTo}>{editing ? "← До оголошення" : "← До оголошень"}</Link>
      <div className="create-page-head">
        <div className="page-heading"><h1>{editing ? "Редагувати оголошення" : "Створити оголошення"}</h1></div>
        <p className="create-lead">{editing ? "Оновіть деталі та фото, щоб оголошення залишалося актуальним." : "Додайте фото, коротко опишіть товар і залиште контакт для покупців."}</p>
      </div>
      <form className="create-form" onSubmit={(event) => void onSubmit(event)}>
        <div className="create-form-grid">
          <section className="form-block photo-block">
            <div className="form-block-head"><span className="form-step">01</span><div><h2>Фото</h2><p className="form-hint">Від 1 до {MAX_PHOTOS}. Перше фото — обкладинка.</p></div></div>
            <div className="photo-grid">
              {photos.map((photo, index) => (
                <div className="photo-tile" key={photo.id}>
                  <img src={photo.preview} alt="" />
                  {index === 0
                    ? <span className="photo-cover">Обкладинка</span>
                    : <button className="photo-make-cover" type="button" onClick={() => makeCover(index)}>Зробити обкладинкою</button>}
                  <button className="photo-crop" type="button" onClick={() => startRecrop(photo)} aria-label={`Обрізати фото ${index + 1}`} title="Обрізати">
                    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 2v14a2 2 0 0 0 2 2h14" /><path d="M18 22V8a2 2 0 0 0-2-2H2" /></svg>
                  </button>
                  <button className="photo-remove" type="button" onClick={() => removePhoto(index)} aria-label={`Прибрати фото ${index + 1}`}>×</button>
                </div>
              ))}
              {photos.length < MAX_PHOTOS && (
                <label className="photo-add">
                  <input type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" multiple onChange={(event) => { addFiles(event.target.files); event.target.value = ""; }} />
                  <span aria-hidden="true">+</span>
                  <small>Додати фото</small>
                </label>
              )}
            </div>
          </section>

          <div className="create-form-fields">
            <section className="form-block">
              <div className="form-block-head"><span className="form-step">02</span><div><h2>Про товар</h2><p className="form-hint">Основна інформація для покупців.</p></div></div>
              <label><span>Назва</span><input value={title} onChange={(event) => setTitle(event.target.value)} minLength={3} maxLength={100} required placeholder="Наприклад, худі з логотипом НаУКМА" /></label>
              <div className="form-row form-row-category">
                <div className="field"><span>Категорія</span><CategorySelect categories={categories} value={categoryId} onChange={setCategoryId} placeholder="Оберіть категорію" otherHint required disabled={editing} /></div>
                <label><span>Стан</span><select value={condition} onChange={(event) => setCondition(event.target.value as ListingCondition)}>
                  {(Object.keys(CONDITION_LABELS) as ListingCondition[]).map((key) => <option value={key} key={key}>{CONDITION_LABELS[key]}</option>)}
                </select></label>
                <label><span>Ціна, грн</span><input type="number" min="0" max={MAX_PRICE} step="1" inputMode="numeric" value={price} onChange={(event) => setPrice(event.target.value)} required placeholder="0" /></label>
              </div>
              {isOtherCategory && (
                <label><span>Своя категорія <small>необов’язково, {SUGGESTION_MIN}–{SUGGESTION_MAX} символів</small></span><input value={suggestedName} onChange={(event) => setSuggestedName(event.target.value)} maxLength={SUGGESTION_MAX} placeholder="Наприклад, музичні інструменти" /><small className="form-hint">Оголошення з’явиться в «Інше», доки адміністратор не схвалить вашу категорію. Одночасно можна мати до 3 пропозицій на розгляді.</small></label>
              )}
              {editing && <p className="form-hint">Категорію після публікації змінити не можна.</p>}
              <label><span>Опис <small>необов’язково</small></span><textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={2000} rows={5} placeholder="Розкажіть про стан, розмір, чому продаєте" /></label>
            </section>

            <section className="form-block contact-block">
              <div className="form-block-head"><span className="form-step">03</span><div><h2>Контакт</h2><p className="form-hint">Його побачать лише авторизовані користувачі.</p></div></div>
              <div className="contact-fields">
                <label><span>Telegram або пошта</span><input value={contact} onChange={(event) => setContact(event.target.value)} minLength={3} maxLength={100} required={!editing || Boolean(initialContact)} placeholder={editing && !initialContact ? "Залиште порожнім, щоб не змінювати" : "@username або name@ukma.edu.ua"} /></label>
                <div className="contact-extra">
                  <label><span>Телефон <small>необов’язково</small></span><input type="tel" inputMode="tel" value={phone} onChange={(event) => setPhone(event.target.value)} maxLength={20} placeholder="+380 50 123 45 67" /></label>
                  <label><span>Локація <small>необов’язково</small></span><input value={location} onChange={(event) => setLocation(event.target.value)} maxLength={60} placeholder="Київ, Контрактова площа" /></label>
                </div>
              </div>
            </section>
          </div>
        </div>

        {formError && <p className="form-error" role="alert">{formError}</p>}
        <div className="form-actions sticky-actions">
          <button className="button button-primary" type="submit" disabled={submitting}>{submitting ? "Зберігаємо…" : editing ? "Зберегти зміни" : "Опублікувати"}</button>
          <Link className="button button-text" to={backTo}>Скасувати</Link>
        </div>
      </form>
    </main>
  );
}

function CreateListingPage({ user, authChecked, categories, onError, onNotice }: {
  user: CurrentUser | null;
  authChecked: boolean;
  categories: Category[];
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}) {
  if (!authChecked) return <PageLoading />;
  if (!user) return <SignInRequired title="Створення оголошення доступне після входу" />;
  return <ListingForm mode="create" initialContact={user.contact ?? ""} categories={categories} onError={onError} onNotice={onNotice} />;
}

function EditListingPage({ user, authChecked, categories, onError, onNotice }: {
  user: CurrentUser | null;
  authChecked: boolean;
  categories: Category[];
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}) {
  const { listingId = "" } = useParams();
  const [listing, setListing] = useState<Listing | null>(null);
  const [existingContact, setExistingContact] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getListing(listingId),
      getSellerContact(listingId).then((item) => item.contact).catch(() => ""),
    ])
      .then(([item, savedContact]) => { setListing(item); setExistingContact(savedContact); })
      .catch(() => setListing(null))
      .finally(() => setLoading(false));
  }, [listingId]);

  if (!authChecked || loading) return <PageLoading />;
  if (!user) return <SignInRequired title="Редагування доступне після входу" />;
  if (!listing) return <NotFoundPage />;
  if (listing.user_id !== user.user_id) {
    return <main className="page-main auth-required"><h1>Це не ваше оголошення</h1><p>Редагувати можна лише власні оголошення.</p><Link className="button button-primary" to={`/listings/${listing.id}`}>До оголошення</Link></main>;
  }
  return <ListingForm mode="edit" listing={listing} initialContact={existingContact} categories={categories} onError={onError} onNotice={onNotice} />;
}

function MyCardContent({ listing, categoryName }: { listing: Listing; categoryName: string }) {
  return (
    <>
      <ListingImage listing={listing} />
      <div className="card-body">
        <div className="card-meta">
          <span>{categoryName}</span>
          <span className={`status-chip status-${listing.status}`}>{STATUS_LABELS[listing.status] ?? listing.status}</span>
        </div>
        <h3>{listing.title}</h3>
        <div className="card-foot">
          <strong className="price">{formatPrice(listing.price)}</strong>
          <span className="condition">{CONDITION_LABELS[listing.condition]}</span>
        </div>
      </div>
    </>
  );
}

function MyListingsPage({ user, authChecked, categoryNames, onError, onNotice }: {
  user: CurrentUser | null;
  authChecked: boolean;
  categoryNames: Map<string, string>;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}) {
  const [items, setItems] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"active" | "archive">("active");
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [workingId, setWorkingId] = useState<string | null>(null);

  useEffect(() => {
    if (!user) { setItems([]); setLoading(false); return; }
    setLoading(true);
    getMyListings().then(setItems).catch((reason) => onError(errorText(reason))).finally(() => setLoading(false));
  }, [user, onError]);

  async function withdraw(id: string) {
    setWorkingId(id);
    try {
      await deleteListing(id);
      setItems((current) => current.map((item) => (item.id === id ? { ...item, status: "WITHDRAWN" } : item)));
      setConfirmId(null);
      onNotice("Оголошення знято з публікації");
    } catch (reason) {
      onError(errorText(reason));
    } finally {
      setWorkingId(null);
    }
  }

  if (!authChecked) return <PageLoading />;
  if (!user) return <SignInRequired title="Ваші оголошення доступні після входу" />;

  const isLive = (item: Listing) => item.status === "ACTIVE" || item.status === "RESERVED";
  const sorted = [...items].sort((a, b) => b.created_at.localeCompare(a.created_at));
  const live = sorted.filter(isLive);
  const archive = sorted.filter((item) => !isLive(item));
  const shown = tab === "active" ? live : archive;

  return (
    <main className="page-main">
      <PageHeading eyebrow="Ваш кабінет" title="Мої оголошення" />
      <div className="my-toolbar">
        <div className="segmented" role="tablist">
          <button type="button" role="tab" aria-selected={tab === "active"} className={tab === "active" ? "active" : ""} onClick={() => setTab("active")}>Активні <b>{live.length}</b></button>
          <button type="button" role="tab" aria-selected={tab === "archive"} className={tab === "archive" ? "active" : ""} onClick={() => setTab("archive")}>Зняті <b>{archive.length}</b></button>
        </div>
        <Link className="button button-primary" to="/listings/new">+ Створити</Link>
      </div>
      {loading ? <ListingSkeleton /> : shown.length === 0 ? (
        <div className="empty-state">
          <span>{tab === "active" ? "+" : "∅"}</span>
          <h3>{tab === "active" ? "Активних оголошень немає" : "Знятих оголошень немає"}</h3>
          <p>{tab === "active" ? "Створіть перше оголошення, і воно зʼявиться тут." : "Тут зʼявляться оголошення, які ви зняли з публікації."}</p>
          {tab === "active" && <Link className="button button-primary" to="/listings/new">Створити оголошення</Link>}
        </div>
      ) : (
        <div className="listing-grid">
          {shown.map((listing) => (
            <article className="listing-card my-card" key={listing.id}>
              {listing.status === "ACTIVE" ? (
                <Link className="card-main" to={`/listings/${listing.id}`}>
                  <MyCardContent listing={listing} categoryName={categoryNames.get(listing.category_id) ?? "Інше"} />
                </Link>
              ) : (
                // Публічний GET /listings/{id} не повертає знятих оголошень, тому посилання лише в активних.
                <div className="card-main card-main-static">
                  <MyCardContent listing={listing} categoryName={categoryNames.get(listing.category_id) ?? "Інше"} />
                </div>
              )}
              {isLive(listing) && (
                <div className="my-actions">
                  {confirmId === listing.id ? (
                    <>
                      <span>Зняти з публікації?</span>
                      <button className="button button-danger" type="button" disabled={workingId === listing.id} onClick={() => void withdraw(listing.id)}>Так, зняти</button>
                      <button className="button button-text" type="button" onClick={() => setConfirmId(null)}>Ні</button>
                    </>
                  ) : (
                    <>
                      <Link className="button button-light" to={`/listings/${listing.id}/edit`}>Редагувати</Link>
                      <button className="button button-text" type="button" onClick={() => setConfirmId(listing.id)}>Зняти</button>
                    </>
                  )}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </main>
  );
}

function ListingGallery({ listing }: { listing: Listing }) {
  const images = useMemo(() => [...listing.images].sort((a, b) => a.display_order - b.display_order), [listing.images]);
  const [index, setIndex] = useState(0);
  const [broken, setBroken] = useState<Set<string>>(() => new Set());

  useEffect(() => { setIndex(0); setBroken(new Set()); }, [listing.id]);

  if (images.length === 0) return <ListingImage listing={listing} large />;
  const count = images.length;
  const current = images[Math.min(index, count - 1)];
  const go = (step: number) => setIndex((value) => (value + step + count) % count);
  const markBroken = (id: string) => setBroken((value) => new Set(value).add(id));

  return (
    <div
      className="gallery"
      tabIndex={0}
      aria-label="Фотографії оголошення"
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft") { event.preventDefault(); go(-1); }
        if (event.key === "ArrowRight") { event.preventDefault(); go(1); }
      }}
    >
      <div className="gallery-stage">
        {broken.has(current.image_id)
          ? <span className="gallery-fallback" aria-hidden="true">Б</span>
          : <img key={current.image_id} src={current.image_url} alt={`Фото ${index + 1} з ${count}`} onError={() => markBroken(current.image_id)} />}
        {count > 1 && (
          <>
            <button className="gallery-nav prev" type="button" onClick={() => go(-1)} aria-label="Попереднє фото">‹</button>
            <button className="gallery-nav next" type="button" onClick={() => go(1)} aria-label="Наступне фото">›</button>
            <span className="gallery-count">{index + 1} / {count}</span>
          </>
        )}
      </div>
      {count > 1 && (
        <div className="gallery-thumbs">
          {images.map((image, position) => (
            <button
              className={position === index ? "active" : ""}
              type="button"
              key={image.image_id}
              onClick={() => setIndex(position)}
              aria-label={`Показати фото ${position + 1}`}
              aria-current={position === index}
            >
              <img
                src={image.thumbnail_url || image.image_url}
                alt=""
                loading="lazy"
                onError={(event) => { if (event.currentTarget.src !== new URL(image.image_url, window.location.href).href) event.currentTarget.src = image.image_url; }}
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function HomePage({ categories, categoryNames, user, favorites, busy, onFavorite, onError }: {
  categories: Category[];
  categoryNames: Map<string, string>;
  user: CurrentUser | null;
  favorites: Set<string>;
  busy: boolean;
  onFavorite: (id: string) => void;
  onError: (message: string) => void;
}) {
  const currentLoginUrl = useCurrentLoginUrl();
  const navigate = useNavigate();
  const [recentListings, setRecentListings] = useState<Listing[]>([]);
  const [totalListings, setTotalListings] = useState<number | null>(null);
  const [freshStat, setFreshStat] = useState<{ value: string; label: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  useEffect(() => {
    getListings(INITIAL_FILTERS, STATS_SAMPLE_SIZE)
      .then((items) => {
        setRecentListings(items.slice(0, 4));
        setTotalListings(items.length);
        const dayAgo = Date.now() - 24 * 60 * 60 * 1000;
        const fresh = items.filter((item) => Date.parse(item.created_at) >= dayAgo).length;
        if (fresh > 0) setFreshStat({ value: String(fresh), label: freshLabel(fresh) });
        else if (items.length) setFreshStat({ value: formatAge(items[0].created_at), label: "останнє оголошення" });
      })
      .catch((requestError) => onError(errorText(requestError)))
      .finally(() => setLoading(false));
  }, [onError]);

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    navigate(q ? `/listings?${new URLSearchParams({ q }).toString()}` : "/listings");
  }

  const totalLabel = totalListings === null
    ? "…"
    : totalListings >= STATS_SAMPLE_SIZE ? `${STATS_SAMPLE_SIZE}+` : String(totalListings);

  return (
    <main>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">Маркетплейс могилянської спільноти</span>
          <h1>Речі знаходять нових власників тут.</h1>
          <p>Купуйте й продавайте всередині НаУКМА: без зайвих чатів, випадкових людей і загублених оголошень.</p>
          <div className="hero-actions">
            <Link className="button button-primary" to="/listings">Переглянути оголошення</Link>
            {!user && <a className="button button-light" href={currentLoginUrl}>Приєднатися</a>}
          </div>
          <div className="trust-row"><span>Вхід з корпоративною поштою НаУКМА</span></div>
        </div>
        <div className="hero-panel">
          <span className="panel-eyebrow">Швидкий пошук</span>
          <h2>Що вам потрібно?</h2>
          <form className="quick-search" onSubmit={submitSearch} role="search">
            <label className="sr-only" htmlFor="hero-search">Пошук оголошень</label>
            <SearchIcon />
            <input id="hero-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Підручник, ноутбук, куртка…" maxLength={100} />
            <button className="button button-primary" type="submit">Знайти</button>
          </form>
          {categories.length > 0 && (
            <div className="chip-row" aria-label="Категорії">
              {categories.slice(0, 6).map((category) => (
                <Link className="chip" key={category.id} to={`/listings?${new URLSearchParams({ category: category.slug }).toString()}`}>{category.name}</Link>
              ))}
            </div>
          )}
          <dl className="stats">
            <div><dd>{totalLabel}</dd><dt>оголошень</dt></div>
            <div><dd>{categories.length}</dd><dt>категорій</dt></div>
            <div><dd>{freshStat?.value ?? "0"}</dd><dt>{freshStat?.label ?? "нових за добу"}</dt></div>
          </dl>
        </div>
      </section>

      <section className="catalog-section recent-section">
        <div className="section-heading">
          <h2>Нещодавні оголошення</h2>
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
          <article>
            <span>01</span><h3>Знайдіть</h3><p>Скористайтеся пошуком і фільтрами каталогу.</p>
            <Link className="button button-light step-button" to="/listings">Відкрити каталог</Link>
          </article>
          <article>
            <span>02</span><h3>Увійдіть</h3><p>Підтвердьте належність до спільноти через Microsoft.</p>
            {user
              ? <div className="step-done">Ви вже увійшли</div>
              : <a className="button button-light step-button" href={loginUrl("/listings")}>Увійти через Microsoft</a>}
          </article>
          <article>
            <span>03</span><h3>Домовтеся</h3><p>Отримайте контакт продавця і напишіть напряму.</p>
            <Link className="button button-light step-button" to="/listings">Обрати оголошення</Link>
          </article>
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
  const filters = useMemo(
    () => filtersFromParams(searchParams, categories),
    [searchParams, categories],
  );
  const [draftFilters, setDraftFilters] = useState<ListingFilters>(filters);
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const requestGeneration = useRef(0);

  useEffect(() => setDraftFilters(filters), [filters]);
  useEffect(() => {
    const categoryParam = searchParams.get("category");
    const category = categories.find((item) => item.id === categoryParam);
    if (!category) return;
    const canonicalParams = new URLSearchParams(searchParams);
    canonicalParams.set("category", category.slug);
    setSearchParams(canonicalParams, { replace: true });
  }, [categories, searchParams, setSearchParams]);
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
    setSearchParams(paramsFromFilters(draftFilters, categories));
  }

  function clearFilters() {
    setDraftFilters(INITIAL_FILTERS);
    setSearchParams(new URLSearchParams());
  }

  return (
    <main className="page-main catalog-page">
      <section>
        <h1 className="sr-only">Оголошення</h1>
        <FilterForm filters={draftFilters} categories={categories} onChange={setDraftFilters} onSubmit={applyFilters} onClear={clearFilters} />
        <div className="results-bar">
          <span className="result-count">{loading ? "Завантаження…" : `Показано: ${listings.length}`}</span>
          {searchParams.toString() !== "" && <button className="link-button" type="button" onClick={clearFilters}>Скинути фільтри</button>}
        </div>
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
  const [open, setOpen] = useState(false);
  return (
    <form className={`filters${open ? " is-open" : ""}`} onSubmit={onSubmit} role="search">
      <label className="search-field">
        <span>Пошук</span>
        <div className="input-icon">
          <SearchIcon />
          <input value={filters.q} onChange={(event) => onChange({ ...filters, q: event.target.value })} placeholder="Що шукаєте?" minLength={1} maxLength={100} />
        </div>
      </label>
      <button className="button button-light filters-toggle" type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        {open ? "Сховати" : "Фільтри"}
      </button>
      <div className="filters-extra">
        <div className="field"><span>Категорія</span><CategorySelect categories={categories} value={filters.categoryId} onChange={(id) => onChange({ ...filters, categoryId: id })} placeholder="Усі категорії" allLabel="Усі категорії" /></div>
        <label><span>Ціна від</span><input type="number" min="0" max={MAX_PRICE} inputMode="numeric" value={filters.minPrice} onChange={(event) => onChange({ ...filters, minPrice: event.target.value })} placeholder="0" /></label>
        <label><span>Ціна до</span><input type="number" min="0" max={MAX_PRICE} inputMode="numeric" value={filters.maxPrice} onChange={(event) => onChange({ ...filters, maxPrice: event.target.value })} placeholder="Будь-яка" /></label>
        <label><span>Сортування</span><select value={filters.sort} onChange={(event) => onChange({ ...filters, sort: event.target.value as ListingFilters["sort"] })}>
          <option value="newest">Спочатку нові</option><option value="oldest">Спочатку старі</option>
          <option value="price_asc">Спочатку дешевші</option><option value="price_desc">Спочатку дорожчі</option>
        </select></label>
      </div>
      <button className="button button-primary filter-submit" type="submit">Знайти</button>
      <button className="button button-text filter-clear" type="button" onClick={onClear}>Скинути</button>
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
              <div className="card-meta">
                <span>{categoryNames.get(listing.category_id) ?? "Інше"}</span>
                <time dateTime={listing.created_at}>{formatAge(listing.created_at)}</time>
              </div>
              <h3>{listing.title}</h3>
              {listing.description && <p>{listing.description}</p>}
              <div className="card-foot">
                <strong className="price">{formatPrice(listing.price)}</strong>
                <span className="condition">{CONDITION_LABELS[listing.condition]}</span>
              </div>
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
  const [contactState, setContactState] = useState<"idle" | "loading" | "failed">("idle");
  const [loading, setLoading] = useState(true);
  const [confirmingWithdraw, setConfirmingWithdraw] = useState(false);
  const [seller, setSeller] = useState<PublicProfile | null>(null);
  const [blockOpen, setBlockOpen] = useState(false);
  const [blockReason, setBlockReason] = useState("");
  const [complaintOpen, setComplaintOpen] = useState(false);
  const userId = user?.user_id ?? null;

  useEffect(() => {
    setLoading(true);
    getListing(listingId).then(setListing).catch((requestError) => onError(errorText(requestError))).finally(() => setLoading(false));
  }, [listingId, onError]);

  useEffect(() => {
    setContact(null);
    if (!userId) { setContactState("idle"); return; }
    let cancelled = false;
    setContactState("loading");
    getSellerContact(listingId)
      .then((item) => { if (!cancelled) { setContact(item.contact); setContactState("idle"); } })
      .catch(() => { if (!cancelled) setContactState("failed"); });
    return () => { cancelled = true; };
  }, [listingId, userId]);

  const sellerId = listing?.user_id ?? null;
  useEffect(() => {
    setSeller(null);
    if (!userId || !sellerId) return;
    let cancelled = false;
    getPublicProfile(sellerId).then((item) => { if (!cancelled) setSeller(item); }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [userId, sellerId]);

  async function withdrawOwn() {
    onBusy(true);
    try { await deleteListing(listingId); onNotice("Оголошення знято з публікації"); navigate("/my"); }
    catch (requestError) { onError(errorText(requestError)); }
    finally { onBusy(false); setConfirmingWithdraw(false); }
  }

  async function blockSeller() {
    if (!listing) return;
    onBusy(true);
    try {
      await blockUser(listing.user_id, blockReason.trim());
      onNotice("Користувача заблоковано");
      setBlockOpen(false);
      setBlockReason("");
    } catch (requestError) { onError(errorText(requestError)); }
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
  const isOwner = Boolean(user && user.user_id === listing.user_id);
  const published = new Date(listing.created_at).toLocaleDateString("uk-UA", { day: "numeric", month: "long", year: "numeric" });
  const sellerName = isOwner ? user?.display_name : seller?.display_name;
  const sellerAvatar = isOwner ? user?.avatar_url : seller?.avatar_url;
  const contactParts = unpackContact(contact ?? "");
  const href = contactParts.main ? contactHref(contactParts.main) : null;
  return (
    <main className="page-main listing-detail-page">
      <Link className="back-link" to="/listings">← До оголошень</Link>
      <div className="ad-layout">
        <section className="ad-card ad-gallery"><ListingGallery listing={listing} /></section>

        <aside className="ad-side">
          <div className="ad-card ad-price-card">
            <time className="ad-date" dateTime={listing.created_at}>Опубліковано {published}</time>
            <h1 className="ad-title">{listing.title}</h1>
            <strong className="ad-price">{formatPrice(listing.price)}</strong>
            <div className="ad-tags"><span>{categoryNames.get(listing.category_id) ?? "Інше"}</span><span>{CONDITION_LABELS[listing.condition]}</span></div>
            <div className="ad-actions">
              {isOwner ? (
                <>
                  <Link className="button button-primary" to={`/listings/${listing.id}/edit`}>Редагувати оголошення</Link>
                  {confirmingWithdraw ? (
                    <div className="confirm-row">
                      <span>Зняти з публікації?</span>
                      <button className="button button-danger" disabled={busy} onClick={() => void withdrawOwn()}>Так, зняти</button>
                      <button className="button button-text" onClick={() => setConfirmingWithdraw(false)}>Ні</button>
                    </div>
                  ) : (
                    <button className="button button-light" disabled={busy} onClick={() => setConfirmingWithdraw(true)}>Зняти з публікації</button>
                  )}
                </>
              ) : (
                <>
                  <button className="button button-light" disabled={busy} onClick={() => onFavorite(listing.id)}>{favorites.has(listing.id) ? "♥ В обраному" : "♡ Додати в обране"}</button>
                  {user ? (
                    <button className="button button-text report-button" type="button" disabled={busy} onClick={() => setComplaintOpen(true)}>Поскаржитись на оголошення</button>
                  ) : (
                    <a className="button button-text report-button" href={currentLoginUrl}>Увійти, щоб поскаржитись</a>
                  )}
                </>
              )}
              {user?.role === "ADMIN" && <button className="button button-danger" disabled={busy} onClick={() => void moderate()}>Зняти з публікації (модератор)</button>}
            </div>
          </div>

          <div className="ad-card ad-seller">
            <h2>{isOwner ? "Ваш контакт" : "Продавець"}</h2>
            <div className="ad-seller-row">
              {sellerName ? (
                <Avatar name={sellerName} url={sellerAvatar} className="ad-avatar-img" />
              ) : (
                <span className="ad-avatar" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4.2 3.6-7 8-7s8 2.8 8 7" /></svg>
                </span>
              )}
              <div><strong>{sellerName ?? "Продавець"}</strong><small>Вхід через корпоративну пошту</small></div>
            </div>
            {!user ? (
              <a className="button button-primary ad-contact-button" href={currentLoginUrl}>Увійти, щоб побачити контакт</a>
            ) : contactState === "loading" ? (
              <div className="ad-contact skeleton-line" aria-busy="true" />
            ) : contact ? (
              <div className="ad-contact">
                <span>Контакт</span>
                {contactParts.main && (href ? <a href={href} target={href.startsWith("http") ? "_blank" : undefined} rel="noreferrer">{contactParts.main}</a> : <strong>{contactParts.main}</strong>)}
                {contactParts.phone && <a href={`tel:${contactParts.phone.replace(/[^\d+]/g, "")}`}>{contactParts.phone}</a>}
                {contactParts.location && <em className="ad-location">{contactParts.location}</em>}
              </div>
            ) : (
              <p className="ad-muted">Контакт зараз недоступний.</p>
            )}
            {user?.role === "ADMIN" && !isOwner && (
              blockOpen ? (
                <form className="admin-inline" onSubmit={(event) => { event.preventDefault(); void blockSeller(); }}>
                  <label><span>Причина блокування</span><textarea value={blockReason} onChange={(event) => setBlockReason(event.target.value)} minLength={5} maxLength={500} required rows={3} /></label>
                  <div className="confirm-row">
                    <button className="button button-danger" type="submit" disabled={busy || blockReason.trim().length < 5}>Заблокувати</button>
                    <button className="button button-text" type="button" onClick={() => setBlockOpen(false)}>Скасувати</button>
                  </div>
                </form>
              ) : (
                <button className="button button-light" type="button" disabled={busy} onClick={() => setBlockOpen(true)}>Заблокувати продавця</button>
              )
            )}
          </div>
        </aside>

        <section className="ad-card ad-info">
          <h2>Опис</h2>
          {listing.description ? <p className="ad-description">{listing.description}</p> : <p className="ad-muted">Продавець не додав опису.</p>}
          <dl className="ad-facts">
            <div><dt>Стан</dt><dd>{CONDITION_LABELS[listing.condition]}</dd></div>
            <div><dt>Категорія</dt><dd>{categoryNames.get(listing.category_id) ?? "Інше"}</dd></div>
            <div><dt>Опубліковано</dt><dd>{published}</dd></div>
          </dl>
        </section>
      </div>
      {complaintOpen && (
        <ComplaintDialog
          listingId={listing.id}
          onClose={() => setComplaintOpen(false)}
          onDone={() => { setComplaintOpen(false); onNotice("Скаргу надіслано адміністраторам"); }}
          onError={onError}
        />
      )}
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

function ProfilePage({ user, authChecked, onUserChange, onError, onNotice }: {
  user: CurrentUser | null;
  authChecked: boolean;
  onUserChange: (user: CurrentUser) => void;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}) {
  const parts = useMemo(() => unpackContact(user?.contact ?? ""), [user?.contact]);
  const [name, setName] = useState(user?.display_name ?? "");
  const [contact, setContact] = useState(parts.main);
  const [phone, setPhone] = useState(parts.phone);
  const [location, setLocation] = useState(parts.location);
  const [saving, setSaving] = useState(false);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [cropFile, setCropFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const loadedFor = useRef<string | null>(user?.user_id ?? null);

  useEffect(() => {
    if (!user || loadedFor.current === user.user_id) return;
    loadedFor.current = user.user_id;
    setName(user.display_name);
    setContact(parts.main);
    setPhone(parts.phone);
    setLocation(parts.location);
  }, [user, parts]);

  const cropSrc = useMemo(() => (cropFile ? URL.createObjectURL(cropFile) : null), [cropFile]);
  useEffect(() => () => { if (cropSrc) URL.revokeObjectURL(cropSrc); }, [cropSrc]);

  if (!authChecked) return <PageLoading />;
  if (!user) return <SignInRequired title="Профіль доступний після входу" />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const trimmedName = name.trim();
    if (!trimmedName) { setFormError("Вкажіть ім’я"); return; }
    if (phone.trim() && !PHONE_PATTERN.test(phone.trim())) {
      setFormError("Перевірте номер телефону: лише цифри, пробіли, дужки й дефіс, можна з «+» на початку");
      return;
    }
    const packed = packContact({ main: contact, phone, location });
    if (packed.length > 200) { setFormError("Контактні дані задовгі, скоротіть їх"); return; }
    setSaving(true);
    try {
      const updated = await updateProfile({ display_name: trimmedName, contact: packed || null });
      onUserChange(updated);
      onNotice("Профіль збережено");
    } catch (requestError) {
      setFormError(errorText(requestError));
    } finally {
      setSaving(false);
    }
  }

  async function sendAvatar(file: File) {
    setAvatarBusy(true);
    try {
      onUserChange(await uploadAvatar(file));
      onNotice("Аватарку оновлено");
    } catch (requestError) {
      onError(errorText(requestError));
    } finally {
      setAvatarBusy(false);
    }
  }

  async function removeAvatar() {
    setAvatarBusy(true);
    try {
      onUserChange(await deleteAvatar());
      onNotice("Аватарку видалено");
    } catch (requestError) {
      onError(errorText(requestError));
    } finally {
      setAvatarBusy(false);
    }
  }

  return (
    <main className="page-main narrow-page">
      <PageHeading eyebrow="Ваш обліковий запис" title="Профіль" />
      <form className="profile-form" onSubmit={(event) => void onSubmit(event)}>
        <section className="form-block profile-top">
          <Avatar name={user.display_name} url={user.avatar_url} className="avatar-xl" />
          <div className="profile-top-info">
            <strong>{user.display_name}</strong>
            <small>{user.role === "ADMIN" ? `${user.email} · Адміністратор` : user.email}</small>
            <div className="profile-avatar-actions">
              <input
                ref={fileInput}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
                hidden
                onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; if (file) setCropFile(file); }}
              />
              <button className="button button-light" type="button" disabled={avatarBusy} onClick={() => fileInput.current?.click()}>{user.avatar_url ? "Змінити фото" : "Додати фото"}</button>
              {user.avatar_url && <button className="button button-text" type="button" disabled={avatarBusy} onClick={() => void removeAvatar()}>Видалити</button>}
            </div>
          </div>
        </section>

        <section className="form-block">
          <div className="form-block-head"><div><h2>Особисті дані</h2><p className="form-hint">Ім’я бачать інші користувачі в оголошеннях.</p></div></div>
          <label><span>Ім’я</span><input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} required /></label>
        </section>

        <section className="form-block contact-block">
          <div className="form-block-head"><div><h2>Контакти</h2><p className="form-hint">Автоматично підставляються у нові оголошення; їх побачать лише авторизовані користувачі.</p></div></div>
          <div className="contact-fields">
            <label><span>Telegram або пошта</span><input value={contact} onChange={(event) => setContact(event.target.value)} maxLength={100} placeholder="@username або name@ukma.edu.ua" /></label>
            <div className="contact-extra">
              <label><span>Телефон <small>необов’язково</small></span><input type="tel" inputMode="tel" value={phone} onChange={(event) => setPhone(event.target.value)} maxLength={20} placeholder="+380 50 123 45 67" /></label>
              <label><span>Локація <small>необов’язково</small></span><input value={location} onChange={(event) => setLocation(event.target.value)} maxLength={60} placeholder="Київ, Контрактова площа" /></label>
            </div>
          </div>
        </section>

        {formError && <p className="form-error" role="alert">{formError}</p>}
        <div className="form-actions sticky-actions">
          <button className="button button-primary" type="submit" disabled={saving}>{saving ? "Зберігаємо…" : "Зберегти профіль"}</button>
          <Link className="button button-text" to="/my">Мої оголошення</Link>
        </div>
      </form>

      {cropFile && cropSrc && (
        <PhotoCropper
          key={cropSrc}
          src={cropSrc}
          name={cropFile.name}
          queued={0}
          aspect={1}
          outputWidth={512}
          title="Оберіть кадр аватарки"
          hint="Квадратний кадр. Перетягніть і змініть масштаб так, щоб обличчя було в центрі."
          onCancel={() => setCropFile(null)}
          onSkip={() => { const file = cropFile; setCropFile(null); void sendAvatar(file); }}
          onUnreadable={() => { setCropFile(null); onError("Не вдалося прочитати це зображення"); }}
          onDone={(blob) => { setCropFile(null); void sendAvatar(new File([blob], "avatar.jpg", { type: "image/jpeg" })); }}
        />
      )}
    </main>
  );
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const UKMA_EMAIL_PATTERN = /^[^@\s]+@ukma\.edu\.ua$/i;

type AdminTab = "moderation" | "complaints" | "feedback" | "blocked" | "user-log" | "admin-log";
/** Кожна вкладка має власну адресу, щоб на неї можна було посилатися. */
const ADMIN_TABS: { id: AdminTab; label: string; path: string }[] = [
  { id: "moderation", label: "Модерація", path: "/admin" },
  { id: "complaints", label: "Скарги", path: "/admin/complaints" },
  { id: "feedback", label: "Звернення", path: "/admin/feedback" },
  { id: "blocked", label: "Заблоковані", path: "/admin/blocked" },
  { id: "user-log", label: "Журнал користувачів", path: "/admin/logs/users" },
  { id: "admin-log", label: "Журнал адмінів", path: "/admin/logs/admins" },
];

function adminTabFromPath(pathname: string): AdminTab | null {
  const clean = pathname.replace(/\/+$/, "") || "/";
  return ADMIN_TABS.find((item) => item.path === clean)?.id ?? null;
}

function AdminPage({ user, authChecked, onError, onNotice, onCategoriesChanged }: {
  user: CurrentUser | null;
  authChecked: boolean;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
  onCategoriesChanged: () => void;
}) {
  const [userId, setUserId] = useState("");
  const [reason, setReason] = useState("");
  const [working, setWorking] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [history, setHistory] = useState<ModerationAction[]>([]);
  const adminLocation = useLocation();
  const tab = adminTabFromPath(adminLocation.pathname);

  if (!authChecked) return <PageLoading />;
  if (!user) return <SignInRequired title="Адмін-панель доступна після входу" />;
  if (user.role !== "ADMIN") {
    return <main className="page-main auth-required"><h1>Немає доступу</h1><p>Адмін-панель доступна лише адміністраторам.</p><Link className="button button-primary" to="/">На головну</Link></main>;
  }

  async function run(action: "block" | "unblock") {
    setFormError(null);
    const id = userId.trim();
    const byEmail = id.includes("@");
    if (byEmail ? !UKMA_EMAIL_PATTERN.test(id) : !UUID_PATTERN.test(id)) {
      setFormError(byEmail ? "Вкажіть адресу у форматі name@ukma.edu.ua" : "Вкажіть коректний ID (UUID) або email @ukma.edu.ua");
      return;
    }
    if (reason.trim().length < 5) { setFormError("Причина має містити щонайменше 5 символів"); return; }
    setWorking(true);
    try {
      const text = reason.trim();
      const result = action === "block"
        ? await (byEmail ? blockUserByEmail(id, text) : blockUser(id, text))
        : await (byEmail ? unblockUserByEmail(id, text) : unblockUser(id, text));
      setHistory((items) => [result, ...items]);
      onNotice(action === "block" ? "Користувача заблоковано" : "Користувача розблоковано");
      setReason("");
    } catch (requestError) {
      onError(errorText(requestError));
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="page-main narrow-page">
      <PageHeading eyebrow="Модерація" title="Адмін-панель" />
      <div className="admin-tabs" role="tablist" aria-label="Розділи адмін-панелі">
        {ADMIN_TABS.map((item) => (
          <Link key={item.id} role="tab" aria-selected={tab === item.id} className={tab === item.id ? "is-active" : ""} to={item.path}>{item.label}</Link>
        ))}
      </div>
      {tab === null && <NotFoundPage />}
      {tab === "complaints" && <ComplaintsPanel onError={onError} onNotice={onNotice} />}
      {tab === "feedback" && <FeedbackAdminPanel onError={onError} onNotice={onNotice} />}
      {tab === "blocked" && <BlockedUsersPanel onError={onError} onNotice={onNotice} />}
      {tab === "user-log" && <ActivityLogPanel kind="users" onError={onError} />}
      {tab === "admin-log" && <ActivityLogPanel kind="admins" onError={onError} />}
      {tab === "moderation" && (<>
      <form className="profile-form" onSubmit={(event) => event.preventDefault()}>
        <section className="form-block">
          <div className="form-block-head"><div><h2>Блокування користувачів</h2><p className="form-hint">Заблокований користувач втрачає чинні сесії й не може входити; його оголошення не видаляються. Зручніше блокувати зі сторінки оголошення кнопкою «Заблокувати продавця».</p></div></div>
          <label><span>Email або ID користувача</span><input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="student@ukma.edu.ua" spellCheck={false} autoComplete="off" /></label>
          <p className="form-hint">Email працює лише для тих, хто вже входив на сайт; інакше буде повідомлення «не знайдено».</p>
          <label><span>Причина <small>5–500 символів</small></span><textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} rows={3} /></label>
          {formError && <p className="form-error" role="alert">{formError}</p>}
          <div className="form-actions">
            <button className="button button-danger" type="button" disabled={working} onClick={() => void run("block")}>Заблокувати</button>
            <button className="button button-light" type="button" disabled={working} onClick={() => void run("unblock")}>Розблокувати</button>
          </div>
        </section>
        {history.length > 0 && (
          <section className="form-block">
            <div className="form-block-head"><div><h2>Дії в цій сесії</h2><p className="form-hint">Повний журнал — у вкладці «Журнал адмінів».</p></div></div>
            <ul className="admin-log">
              {history.map((item) => (
                <li key={item.id}>
                  <strong>{item.action_type === "BLOCK_USER" ? "Заблоковано" : "Розблоковано"}</strong>
                  <code>{item.target_user_id}</code>
                  <span>{item.reason}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </form>
      <CategorySuggestionsPanel onError={onError} onNotice={onNotice} onCategoriesChanged={onCategoriesChanged} />
      </>)}
    </main>
  );
}

const OTHER_CATEGORY_ID = "55555555-5555-5555-5555-555555555555";

/** Категорія «Інше» завжди остання; решта лишається в порядку сервера. */
function sortCategories(items: Category[]): Category[] {
  return [...items].sort((a, b) => Number(a.id === OTHER_CATEGORY_ID) - Number(b.id === OTHER_CATEGORY_ID));
}

function CategorySelect({ categories, value, onChange, placeholder, allLabel, otherHint = false, required = false, disabled = false }: {
  categories: Category[];
  value: string;
  onChange: (id: string) => void;
  placeholder: string;
  allLabel?: string;
  /** У формі оголошення біля «Інше» підказує, що можна запропонувати власну категорію. */
  otherHint?: boolean;
  required?: boolean;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const options = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("uk");
    const matched = categories.filter((category) => category.name.toLocaleLowerCase("uk").includes(needle));
    return allLabel && !needle ? [{ id: "", name: allLabel }, ...matched] : matched;
  }, [categories, query, allLabel]);

  useEffect(() => {
    if (!open) return;
    searchRef.current?.focus();
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  const selectedName = categories.find((category) => category.id === value)?.name ?? (value === "" ? "" : value);

  function choose(id: string) {
    onChange(id);
    setOpen(false);
    setQuery("");
  }

  function onSearchKeyDown(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") { event.preventDefault(); setActive((index) => Math.min(index + 1, options.length - 1)); }
    else if (event.key === "ArrowUp") { event.preventDefault(); setActive((index) => Math.max(index - 1, 0)); }
    else if (event.key === "Enter") { event.preventDefault(); if (options[active]) choose(options[active].id); }
    else if (event.key === "Escape") { event.preventDefault(); setOpen(false); }
  }

  return (
    <div className="category-select" ref={rootRef}>
      <button className="category-select-button" type="button" disabled={disabled} aria-haspopup="listbox" aria-expanded={open} onClick={() => { setOpen((current) => !current); setActive(0); }}>
        <span className={selectedName ? "" : "category-select-placeholder"}>{selectedName || placeholder}</span>
      </button>
      {required && <input className="category-select-required" tabIndex={-1} aria-hidden="true" required value={value} onChange={() => undefined} />}
      {open && (
        <div className="category-select-popover">
          <input ref={searchRef} className="category-select-search" type="search" value={query} onChange={(event) => { setQuery(event.target.value); setActive(0); }} onKeyDown={onSearchKeyDown} placeholder="Пошук категорії" aria-label="Пошук категорії" />
          <ul role="listbox">
            {options.map((option, index) => (
              <li key={option.id || "all"} role="option" aria-selected={option.id === value} className={index === active ? "is-active" : ""} onMouseEnter={() => setActive(index)} onMouseDown={(event) => { event.preventDefault(); choose(option.id); }}>{option.name}{otherHint && option.id === OTHER_CATEGORY_ID && <small className="category-option-hint"> (або запропонуйте свою)</small>}</li>
            ))}
            {options.length === 0 && <li className="category-select-empty">Нічого не знайдено</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
const SUGGESTION_MIN = 2;
const SUGGESTION_MAX = 40;

function CategorySuggestionsPanel({ onError, onNotice, onCategoriesChanged }: {
  onError: (message: string) => void;
  onNotice: (message: string) => void;
  onCategoriesChanged: () => void;
}) {
  const [items, setItems] = useState<CategorySuggestion[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await getCategorySuggestions("PENDING"));
    } catch (requestError) {
      setItems([]);
      onError(errorText(requestError));
    }
  }, [onError]);

  useEffect(() => { void load(); }, [load]);

  async function approve(item: CategorySuggestion) {
    const edited = (names[item.suggestion_id] ?? item.name).trim();
    if (edited.length < SUGGESTION_MIN || edited.length > SUGGESTION_MAX) { onError(`Назва категорії: від ${SUGGESTION_MIN} до ${SUGGESTION_MAX} символів`); return; }
    setBusyId(item.suggestion_id);
    try {
      await approveCategorySuggestion(item.suggestion_id, edited === item.name ? undefined : edited);
      onNotice(`Категорію «${edited}» створено, оголошення перенесено`);
      onCategoriesChanged();
      await load();
    } catch (requestError) {
      onError(errorText(requestError));
    } finally {
      setBusyId(null);
    }
  }

  async function reject(item: CategorySuggestion) {
    const reason = (reasons[item.suggestion_id] ?? "").trim();
    if (reason.length < 5) { onError("Вкажіть причину відхилення (щонайменше 5 символів)"); return; }
    setBusyId(item.suggestion_id);
    try {
      await rejectCategorySuggestion(item.suggestion_id, reason);
      onNotice("Пропозицію відхилено");
      await load();
    } catch (requestError) {
      onError(errorText(requestError));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="form-block suggestions-panel">
      <div className="form-block-head"><div><h2>Пропозиції категорій</h2><p className="form-hint">Схвалення створює категорію й переносить оголошення з «Інше»; назву можна виправити. Відхилення лишає оголошення в «Інше».</p></div></div>
      {items === null && <p className="form-hint">Завантажуємо…</p>}
      {items?.length === 0 && <p className="form-hint">Нових пропозицій немає.</p>}
      <ul className="suggestion-list">
        {items?.map((item) => (
          <li key={item.suggestion_id}>
            <div className="suggestion-head"><strong>{item.name}</strong><span className="form-hint">оголошень: {item.listings_count}</span></div>
            <div className="form-row">
              <label><span>Назва категорії</span><input value={names[item.suggestion_id] ?? item.name} maxLength={SUGGESTION_MAX} onChange={(event) => setNames((current) => ({ ...current, [item.suggestion_id]: event.target.value }))} /></label>
              <label><span>Причина відхилення</span><input value={reasons[item.suggestion_id] ?? ""} maxLength={500} onChange={(event) => setReasons((current) => ({ ...current, [item.suggestion_id]: event.target.value }))} placeholder="Для відхилення" /></label>
            </div>
            <div className="form-actions">
              <button className="button button-primary" type="button" disabled={busyId === item.suggestion_id} onClick={() => void approve(item)}>Схвалити</button>
              <button className="button button-danger" type="button" disabled={busyId === item.suggestion_id} onClick={() => void reject(item)}>Відхилити</button>
            </div>
          </li>
        ))}
      </ul>
    </section>
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
  const count = listing.images.length;
  return <div className={`listing-image ${large ? "large" : ""} ${!source || failed ? "fallback" : ""}`}>{source && !failed ? <img src={source} alt="" onError={() => setFailed(true)} /> : <span aria-hidden="true">Б</span>}{!large && count > 1 && <span className="photo-count" aria-label={`Фото: ${count}`}>{count} фото</span>}</div>;
}

function Footer() {
  return <footer><Link className="brand footer-brand" to="/" aria-label="Барахолка НаУКМА, на головну"><span className="brand-mark">Б</span><span className="brand-divider" aria-hidden="true" /><NaukmaLogo className="naukma-logo" /></Link><p>Проєкт створюється в рамках курсу SSDM 2026 · Без платежів і доставки всередині сервісу · <Link to="/feedback">Зворотний зв'язок</Link></p></footer>;
}

export default App;
