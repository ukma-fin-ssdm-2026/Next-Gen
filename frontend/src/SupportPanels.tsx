import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ApiError,
  getActivityLog,
  getBlockedUsers,
  getComplaints,
  getFeedback,
  resolveComplaint,
  resolveFeedback,
  submitComplaint,
  submitFeedback,
  unblockUser,
} from "./api";
import type {
  BlockedStatus,
  BlockedUser,
  Complaint,
  ComplaintReason,
  CurrentUser,
  FeedbackMessage,
  LogEntry,
} from "./types";

function describe(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Щось пішло не так. Спробуйте ще раз.";
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("uk-UA", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export const COMPLAINT_REASON_LABELS: Record<ComplaintReason, string> = {
  SPAM: "Спам або реклама",
  FRAUD: "Підозра на шахрайство",
  PROHIBITED: "Заборонений товар",
  INAPPROPRIATE: "Неприйнятний вміст",
  WRONG_CATEGORY: "Хибна категорія",
  OTHER: "Інше",
};

const COMPLAINT_STATUS_LABELS = { OPEN: "Нова", RESOLVED: "Розглянута", DISMISSED: "Відхилена" } as const;

const ACTION_LABELS: Record<string, string> = {
  LISTING_CREATED: "Створив оголошення",
  LISTING_UPDATED: "Змінив оголошення",
  LISTING_WITHDRAWN: "Зняв оголошення",
  FAVORITE_ADDED: "Додав в обране",
  FAVORITE_REMOVED: "Прибрав з обраного",
  COMPLAINT_SUBMITTED: "Подав скаргу",
  COMPLAINT_RESOLVED: "Розглянув скаргу",
  COMPLAINT_DISMISSED: "Відхилив скаргу",
  FEEDBACK_SUBMITTED: "Надіслав звернення",
  FEEDBACK_RESOLVED: "Опрацював звернення",
  PROFILE_UPDATED: "Оновив профіль",
  WITHDRAW_LISTING: "Зняв оголошення (модерація)",
  BLOCK_USER: "Заблокував користувача",
  UNBLOCK_USER: "Розблокував користувача",
  APPROVE_CATEGORY: "Схвалив категорію",
  REJECT_CATEGORY: "Відхилив категорію",
};

/** Вікно скарги на оголошення (FR-016). */
export function ComplaintDialog({ listingId, onClose, onDone, onError }: {
  listingId: string;
  onClose: () => void;
  onDone: () => void;
  onError: (message: string) => void;
}) {
  const [reason, setReason] = useState<ComplaintReason>("SPAM");
  const [details, setDetails] = useState("");
  const [sending, setSending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (reason === "OTHER" && details.trim().length === 0) { setFormError("Опишіть проблему, якщо обрана причина «Інше»"); return; }
    setSending(true);
    setFormError(null);
    try {
      await submitComplaint(listingId, reason, details.trim());
      onDone();
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 409) { onError(describe(requestError)); onClose(); }
      else setFormError(describe(requestError));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <form className="dialog-card" role="dialog" aria-modal="true" aria-labelledby="complaint-title" onSubmit={(event) => void submit(event)}>
        <h2 id="complaint-title">Поскаржитись на оголошення</h2>
        <p className="form-hint">Скаргу побачать адміністратори. Від одного користувача на оголошення приймається одна скарга.</p>
        <label><span>Причина</span>
          <select value={reason} onChange={(event) => setReason(event.target.value as ComplaintReason)}>
            {(Object.keys(COMPLAINT_REASON_LABELS) as ComplaintReason[]).map((key) => <option key={key} value={key}>{COMPLAINT_REASON_LABELS[key]}</option>)}
          </select>
        </label>
        <label><span>Деталі <small>{reason === "OTHER" ? "обов'язково, до 500 символів" : "необов'язково, до 500 символів"}</small></span>
          <textarea value={details} maxLength={500} rows={4} onChange={(event) => setDetails(event.target.value)} />
        </label>
        {formError && <p className="form-error" role="alert">{formError}</p>}
        <div className="form-actions">
          <button className="button button-danger" type="submit" disabled={sending}>Надіслати скаргу</button>
          <button className="button button-light" type="button" onClick={onClose}>Скасувати</button>
        </div>
      </form>
    </div>
  );
}

/** Форма звернення до адміністрації (FR-017). */
export function FeedbackPage({ user, authChecked, loginHref, onError, onNotice }: {
  user: CurrentUser | null;
  authChecked: boolean;
  loginHref: string;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}) {
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  if (!authChecked) return <main className="page-main narrow-page" />;
  if (!user) {
    return <main className="page-main auth-required"><span className="brand-mark large-mark">Б</span><h1>Звернення доступне після входу</h1><p>Увійдіть через корпоративний Microsoft-акаунт НаУКМА.</p><a className="button button-primary" href={loginHref}>Увійти через Microsoft</a></main>;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const cleanSubject = subject.trim();
    const cleanMessage = message.trim();
    if (cleanSubject.length < 3) { setFormError("Тема має містити щонайменше 3 символи"); return; }
    if (cleanMessage.length < 10) { setFormError("Повідомлення має містити щонайменше 10 символів"); return; }
    setSending(true);
    setFormError(null);
    try {
      await submitFeedback(cleanSubject, cleanMessage);
      setSent(true);
      setSubject("");
      setMessage("");
      onNotice("Звернення надіслано адміністрації");
    } catch (requestError) {
      onError(describe(requestError));
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="page-main narrow-page">
      <div className="page-heading"><span className="eyebrow dark">Підтримка</span><h1>Написати адміністрації</h1></div>
      <form className="profile-form" onSubmit={(event) => void submit(event)}>
        <section className="form-block">
          <div className="form-block-head"><div><h2>Ваше звернення</h2><p className="form-hint">Пропозиції, питання щодо блокування чи проблеми із сервісом. Адміністрація побачить звернення в адмін-панелі.</p></div></div>
          {sent && <p className="form-success" role="status">Дякуємо! Звернення отримано. <Link to="/">На головну</Link></p>}
          <label><span>Тема <small>3–120 символів</small></span><input value={subject} maxLength={120} onChange={(event) => setSubject(event.target.value)} /></label>
          <label><span>Повідомлення <small>10–2000 символів</small></span><textarea value={message} maxLength={2000} rows={7} onChange={(event) => setMessage(event.target.value)} /></label>
          {formError && <p className="form-error" role="alert">{formError}</p>}
          <div className="form-actions"><button className="button button-primary" type="submit" disabled={sending}>Надіслати</button></div>
        </section>
      </form>
    </main>
  );
}

/** Вікно для заблокованого користувача: факт і причина блокування (FR-013). */
export function BlockedNotice({ status, busy, onLogout }: { status: BlockedStatus; busy: boolean; onLogout: () => void }) {
  return (
    <div className="modal-backdrop blocked-backdrop" role="presentation">
      <div className="dialog-card blocked-card" role="alertdialog" aria-modal="true" aria-labelledby="blocked-title" aria-describedby="blocked-reason">
        <span className="blocked-icon" aria-hidden="true">!</span>
        <h2 id="blocked-title">Ваш обліковий запис заблоковано</h2>
        <p className="form-hint">Адміністратор обмежив доступ до «Барахолки НаУКМА». Створювати оголошення та користуватися сервісом поки що неможливо.</p>
        <dl className="blocked-details">
          <div><dt>Причина</dt><dd id="blocked-reason">{status.reason?.trim() || "Причину не вказано"}</dd></div>
          <div><dt>Дата блокування</dt><dd>{formatDateTime(status.blocked_at)}</dd></div>
        </dl>
        <p className="form-hint">Якщо вважаєте, що це помилка, зверніться до адміністрації НаУКМА.</p>
        <div className="form-actions"><button className="button button-primary" type="button" disabled={busy} onClick={onLogout}>Зрозуміло, вийти</button></div>
      </div>
    </div>
  );
}

function useList<T>(loader: () => Promise<T[]>, onError: (message: string) => void) {
  const [items, setItems] = useState<T[] | null>(null);
  const load = useCallback(async () => {
    try {
      setItems(await loader());
    } catch (requestError) {
      setItems([]);
      onError(describe(requestError));
    }
  }, [loader, onError]);
  useEffect(() => { void load(); }, [load]);
  return { items, reload: load };
}

export function ComplaintsPanel({ onError, onNotice }: { onError: (m: string) => void; onNotice: (m: string) => void }) {
  const loader = useCallback(() => getComplaints(), []);
  const { items, reload } = useList<Complaint>(loader, onError);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  async function resolve(item: Complaint, status: "RESOLVED" | "DISMISSED") {
    setBusyId(item.id);
    try {
      await resolveComplaint(item.id, status, (notes[item.id] ?? "").trim());
      onNotice(status === "RESOLVED" ? "Скаргу позначено розглянутою" : "Скаргу відхилено");
      await reload();
    } catch (requestError) {
      onError(describe(requestError));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="form-block">
      <div className="form-block-head"><div><h2>Скарги на оголошення</h2><p className="form-hint">Нові скарги першими. Зняти оголошення чи заблокувати продавця можна зі сторінки оголошення.</p></div></div>
      {items === null && <p className="form-hint">Завантажуємо…</p>}
      {items?.length === 0 && <p className="form-hint">Скарг поки немає.</p>}
      <ul className="suggestion-list">
        {items?.map((item) => (
          <li key={item.id}>
            <div className="suggestion-head">
              <strong><Link to={`/listings/${item.listing_id}`}>{item.listing_title ?? "Оголошення"}</Link></strong>
              <span className={`status-chip status-${item.status.toLowerCase()}`}>{COMPLAINT_STATUS_LABELS[item.status]}</span>
            </div>
            <p className="form-hint">{COMPLAINT_REASON_LABELS[item.reason]} · від {item.reporter_email ?? "невідомо"} · {formatDateTime(item.created_at)}</p>
            {item.details && <p className="log-details">{item.details}</p>}
            {item.status === "OPEN" ? (
              <>
                <label><span>Примітка <small>необов'язково</small></span><input value={notes[item.id] ?? ""} maxLength={500} onChange={(event) => setNotes((current) => ({ ...current, [item.id]: event.target.value }))} /></label>
                <div className="form-actions">
                  <button className="button button-primary" type="button" disabled={busyId === item.id} onClick={() => void resolve(item, "RESOLVED")}>Розглянуто</button>
                  <button className="button button-light" type="button" disabled={busyId === item.id} onClick={() => void resolve(item, "DISMISSED")}>Відхилити</button>
                </div>
              </>
            ) : item.resolution_note ? <p className="form-hint">Примітка: {item.resolution_note}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function FeedbackAdminPanel({ onError, onNotice }: { onError: (m: string) => void; onNotice: (m: string) => void }) {
  const loader = useCallback(() => getFeedback(), []);
  const { items, reload } = useList<FeedbackMessage>(loader, onError);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function resolve(item: FeedbackMessage) {
    setBusyId(item.id);
    try {
      await resolveFeedback(item.id);
      onNotice("Звернення опрацьовано");
      await reload();
    } catch (requestError) {
      onError(describe(requestError));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="form-block">
      <div className="form-block-head"><div><h2>Звернення до адміністрації</h2><p className="form-hint">Нові звернення першими.</p></div></div>
      {items === null && <p className="form-hint">Завантажуємо…</p>}
      {items?.length === 0 && <p className="form-hint">Звернень поки немає.</p>}
      <ul className="suggestion-list">
        {items?.map((item) => (
          <li key={item.id}>
            <div className="suggestion-head">
              <strong>{item.subject}</strong>
              <span className={`status-chip status-${item.status === "NEW" ? "open" : "resolved"}`}>{item.status === "NEW" ? "Нове" : "Опрацьоване"}</span>
            </div>
            <p className="form-hint">{item.user_email ?? "невідомо"} · {formatDateTime(item.created_at)}</p>
            <p className="log-details">{item.message}</p>
            {item.status === "NEW" && (
              <div className="form-actions"><button className="button button-primary" type="button" disabled={busyId === item.id} onClick={() => void resolve(item)}>Позначити опрацьованим</button></div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function BlockedUsersPanel({ onError, onNotice }: { onError: (m: string) => void; onNotice: (m: string) => void }) {
  const loader = useCallback(() => getBlockedUsers(), []);
  const { items, reload } = useList<BlockedUser>(loader, onError);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  async function unblock(item: BlockedUser) {
    const reason = (reasons[item.user_id] ?? "").trim();
    if (reason.length < 5) { onError("Вкажіть причину розблокування (щонайменше 5 символів)"); return; }
    setBusyId(item.user_id);
    try {
      await unblockUser(item.user_id, reason);
      onNotice("Користувача розблоковано");
      await reload();
    } catch (requestError) {
      onError(describe(requestError));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="form-block">
      <div className="form-block-head"><div><h2>Заблоковані користувачі</h2><p className="form-hint">Список зберігається в базі даних разом із причиною блокування.</p></div></div>
      {items === null && <p className="form-hint">Завантажуємо…</p>}
      {items?.length === 0 && <p className="form-hint">Заблокованих користувачів немає.</p>}
      <ul className="suggestion-list">
        {items?.map((item) => (
          <li key={item.user_id}>
            <div className="suggestion-head"><strong>{item.display_name}</strong><span className="form-hint">{formatDateTime(item.blocked_at)}</span></div>
            <p className="form-hint">{item.email}</p>
            <p className="log-details"><b>Причина:</b> {item.reason?.trim() || "не вказано"}</p>
            <label><span>Причина розблокування <small>5–500 символів</small></span><input value={reasons[item.user_id] ?? ""} maxLength={500} onChange={(event) => setReasons((current) => ({ ...current, [item.user_id]: event.target.value }))} /></label>
            <div className="form-actions"><button className="button button-light" type="button" disabled={busyId === item.user_id} onClick={() => void unblock(item)}>Розблокувати</button></div>
          </li>
        ))}
      </ul>
    </section>
  );
}

type LogGroup = "listings" | "favorites" | "profile" | "complaints" | "feedback" | "users" | "categories";

/** Логічні категорії записів журналу: до якої групи належить тип дії. */
const LOG_GROUPS: { id: LogGroup; label: string; actions: string[] }[] = [
  { id: "listings", label: "Оголошення", actions: ["LISTING_CREATED", "LISTING_UPDATED", "LISTING_WITHDRAWN", "WITHDRAW_LISTING"] },
  { id: "favorites", label: "Обране", actions: ["FAVORITE_ADDED", "FAVORITE_REMOVED"] },
  { id: "profile", label: "Профіль", actions: ["PROFILE_UPDATED"] },
  { id: "complaints", label: "Скарги", actions: ["COMPLAINT_SUBMITTED", "COMPLAINT_RESOLVED", "COMPLAINT_DISMISSED"] },
  { id: "feedback", label: "Звернення", actions: ["FEEDBACK_SUBMITTED", "FEEDBACK_RESOLVED"] },
  { id: "users", label: "Користувачі (блокування)", actions: ["BLOCK_USER", "UNBLOCK_USER"] },
  { id: "categories", label: "Категорії", actions: ["APPROVE_CATEGORY", "REJECT_CATEGORY"] },
];

function groupOf(action: string): LogGroup | null {
  return LOG_GROUPS.find((group) => group.actions.includes(action))?.id ?? null;
}

/** Журнал дій: окремо для користувачів і для адміністраторів (FR-018). */
export function ActivityLogPanel({ kind, onError }: { kind: "users" | "admins"; onError: (m: string) => void }) {
  const loader = useCallback(() => getActivityLog(kind, 0, 500), [kind]);
  const { items, reload } = useList<LogEntry>(loader, onError);
  // Пошук і категорія зберігаються в адресі (?q=…&category=…), щоб ділитися посиланням.
  const [params, setParams] = useSearchParams();
  const rawGroup = params.get("category");
  const group: LogGroup | "all" = LOG_GROUPS.some((item) => item.id === rawGroup) ? (rawGroup as LogGroup) : "all";
  const query = params.get("q") ?? "";
  const updateParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next, { replace: true });
  };
  const title = kind === "users" ? "Журнал дій користувачів" : "Журнал дій адміністраторів";

  const visibleGroups = useMemo(() => {
    const present = new Set((items ?? []).map((entry) => groupOf(entry.action_type)));
    return LOG_GROUPS.filter((item) => present.has(item.id) || item.id === group);
  }, [items, group]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("uk");
    return (items ?? []).filter((entry) => {
      if (group !== "all" && groupOf(entry.action_type) !== group) return false;
      if (!needle) return true;
      const haystack = [ACTION_LABELS[entry.action_type] ?? entry.action_type, entry.actor_email, entry.target_email, entry.details]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("uk");
      return haystack.includes(needle);
    });
  }, [items, group, query]);

  return (
    <section className="form-block">
      <div className="form-block-head">
        <div><h2>{title}</h2><p className="form-hint">Останні 500 записів, нові першими. Записи незмінні.</p></div>
        <button className="button button-light" type="button" onClick={() => void reload()}>Оновити</button>
      </div>
      <div className="log-toolbar">
        <input type="search" className="log-search" value={query} onChange={(event) => updateParam("q", event.target.value)} placeholder="Пошук за email, дією або описом" aria-label="Пошук у журналі" />
        <select className="log-filter" value={group} onChange={(event) => updateParam("category", event.target.value === "all" ? "" : event.target.value)} aria-label="Категорія записів">
          <option value="all">Усі категорії</option>
          {visibleGroups.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </div>
      {items === null && <p className="form-hint">Завантажуємо…</p>}
      {items !== null && items.length === 0 && <p className="form-hint">Записів поки немає.</p>}
      {items !== null && items.length > 0 && filtered.length === 0 && <p className="form-hint">За цим пошуком і фільтром нічого не знайдено.</p>}
      {items !== null && items.length > 0 && <p className="form-hint">Показано {filtered.length} із {items.length}</p>}
      <ul className="admin-log">
        {filtered.map((entry) => (
          <li key={entry.id}>
            <strong>{ACTION_LABELS[entry.action_type] ?? entry.action_type}<span className="log-group-chip">{LOG_GROUPS.find((item) => item.id === groupOf(entry.action_type))?.label ?? "Інше"}</span></strong>
            <span>{entry.actor_email ?? entry.actor_id}{entry.target_email ? ` → ${entry.target_email}` : ""}</span>
            {entry.listing_id && <Link to={`/listings/${entry.listing_id}`}>оголошення</Link>}
            {entry.details && <span className="log-details">{entry.details}</span>}
            <code>{formatDateTime(entry.created_at)}</code>
          </li>
        ))}
      </ul>
    </section>
  );
}
