import { FormEvent, KeyboardEvent, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  getConversations,
  getMessages,
  getUnreadCount,
  markConversationRead,
  sendChatMessage,
  startConversation,
} from "./api";
import { MessageReportDialog } from "./SupportPanels";
import type { ChatConversation, ChatListingCard, ChatMessage, CurrentUser } from "./types";
import "./chat.css";

const MESSAGE_MAX = 1000;
/** Інтервали опитування за ADR-005: відкрита розмова — 5 с, список і значок — 30 с. */
const THREAD_POLL_MS = 5_000;
const LIST_POLL_MS = 30_000;
/** Подія, якою компоненти повідомляють один одного, що лічильники й список застаріли. */
export const CHAT_CHANGED_EVENT = "baraholka:chat-changed";

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "Не вдалося виконати запит";
}

function notifyChatChanged() { window.dispatchEvent(new Event(CHAT_CHANGED_EVENT)); }

function formatPrice(price: number): string {
  return new Intl.NumberFormat("uk-UA", { style: "currency", currency: "UAH", maximumFractionDigits: 0 }).format(price);
}

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** Короткий час для списку: сьогодні — година, інакше дата. */
function listTime(iso: string): string {
  const date = new Date(iso);
  if (sameDay(date, new Date())) return date.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" });
  return date.toLocaleDateString("uk-UA", { day: "numeric", month: "short" });
}

function dayLabel(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  if (sameDay(date, now)) return "Сьогодні";
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(date, yesterday)) return "Вчора";
  return date.toLocaleDateString("uk-UA", { day: "numeric", month: "long", year: date.getFullYear() === now.getFullYear() ? undefined : "numeric" });
}

function ChatAvatar({ name, url, size = 40 }: { name: string; url?: string | null; size?: number }) {
  return (
    <span className="chat-avatar" style={{ width: size, height: size, fontSize: size * 0.42 }} aria-hidden="true">
      {url ? <img src={url} alt="" /> : (name.trim().slice(0, 1) || "?").toUpperCase()}
    </span>
  );
}

/** Кількість непрочитаних для значка в шапці: опитування раз на 30 с і за подією змін чату. */
export function useUnreadCount(user: CurrentUser | null): number {
  const [count, setCount] = useState(0);
  const userId = user?.user_id ?? null;
  useEffect(() => {
    if (!userId) { setCount(0); return; }
    let cancelled = false;
    const load = () => {
      if (document.hidden) return;
      getUnreadCount().then((value) => { if (!cancelled) setCount(value); }).catch(() => undefined);
    };
    load();
    const timer = window.setInterval(load, LIST_POLL_MS);
    window.addEventListener(CHAT_CHANGED_EVENT, load);
    document.addEventListener("visibilitychange", load);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.removeEventListener(CHAT_CHANGED_EVENT, load);
      document.removeEventListener("visibilitychange", load);
    };
  }, [userId]);
  return count;
}

export function MessageIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" aria-hidden="true">
      <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9 9 0 0 1-3.4-.7L3 21l1.9-5.2A8.4 8.4 0 1 1 21 11.5Z" />
    </svg>
  );
}

/** Діалог «Написати продавцю» на сторінці оголошення: створює розмову з першим повідомленням. */
export function ContactSellerDialog({ listingId, sellerName, onClose, onError }: {
  listingId: string;
  sellerName?: string;
  onClose: () => void;
  onError: (message: string) => void;
}) {
  const navigate = useNavigate();
  const [text, setText] = useState("Вітаю! Чи актуальне ще це оголошення?");
  const [sending, setSending] = useState(false);
  const trimmed = text.trim();

  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape" && !sending) onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, sending]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!trimmed || sending) return;
    setSending(true);
    try {
      const result = await startConversation(listingId, trimmed);
      notifyChatChanged();
      navigate(`/messages/${result.conversation_id}`);
    } catch (requestError) {
      onError(errorText(requestError));
      setSending(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !sending) onClose(); }}>
      <form className="dialog-card chat-start-dialog" role="dialog" aria-modal="true" aria-labelledby="chat-start-title" onSubmit={(event) => void submit(event)}>
        <h2 id="chat-start-title">Написати {sellerName ? `користувачу ${sellerName}` : "продавцю"}</h2>
        <p className="form-hint">Повідомлення побачить лише продавець. Разом із ним надішлеться картка цього оголошення.</p>
        <label>
          <span>Повідомлення</span>
          <textarea value={text} onChange={(event) => setText(event.target.value)} maxLength={MESSAGE_MAX} rows={4} autoFocus required />
        </label>
        <small className="chat-counter">{text.length}/{MESSAGE_MAX}</small>
        <div className="form-actions">
          <button className="button button-primary" type="submit" disabled={sending || !trimmed}>{sending ? "Надсилаємо…" : "Надіслати"}</button>
          <button className="button button-text" type="button" disabled={sending} onClick={onClose}>Скасувати</button>
        </div>
      </form>
    </div>
  );
}

function ListingCardView({ card }: { card: ChatListingCard }) {
  if (!card.available) {
    return <div className="chat-listing-card is-gone"><span>Оголошення знято</span></div>;
  }
  return (
    <Link className="chat-listing-card" to={`/listings/${card.listing_id}`}>
      {card.image_url ? <img src={card.image_url} alt="" /> : <span className="chat-listing-thumb" aria-hidden="true">Б</span>}
      <span className="chat-listing-info">
        <strong>{card.title}</strong>
        {card.price !== null && <span>{formatPrice(card.price)}</span>}
      </span>
    </Link>
  );
}

function ConversationList({ conversations, activeId, loading, hasMore, onMore }: {
  conversations: ChatConversation[];
  activeId?: string;
  loading: boolean;
  hasMore: boolean;
  onMore: () => void;
}) {
  if (loading) return <div className="chat-list-state" aria-busy="true">Завантажуємо…</div>;
  if (conversations.length === 0) {
    return (
      <div className="chat-list-state">
        <strong>Розмов поки немає</strong>
        <p>Відкрийте оголошення й натисніть «Написати продавцю».</p>
        <Link className="button button-light" to="/listings">До оголошень</Link>
      </div>
    );
  }
  return (
    <ul className="chat-list">
      {conversations.map((item) => (
        <li key={item.conversation_id}>
          <Link className={`chat-list-item${item.conversation_id === activeId ? " is-active" : ""}`} to={`/messages/${item.conversation_id}`}>
            <ChatAvatar name={item.other.display_name} url={item.other.avatar_url} />
            <span className="chat-list-text">
              <span className="chat-list-top">
                <strong>{item.other.display_name}</strong>
                <time dateTime={item.last_message_at}>{listTime(item.last_message_at)}</time>
              </span>
              <span className="chat-list-bottom">
                <span className="chat-list-preview">
                  {item.last_message ? `${item.last_message.is_own ? "Ви: " : ""}${item.last_message.body}` : "Розмову розпочато"}
                </span>
                {item.unread_count > 0 && <span className="chat-unread" aria-label={`Непрочитаних: ${item.unread_count}`}>{item.unread_count > 99 ? "99+" : item.unread_count}</span>}
              </span>
            </span>
          </Link>
        </li>
      ))}
      {hasMore && <li><button className="button button-text chat-more" type="button" onClick={onMore}>Показати ще</button></li>}
    </ul>
  );
}

function Thread({ conversation, onError, onNotice }: { conversation: ChatConversation | null; onError: (message: string) => void; onNotice: (message: string) => void }) {
  const conversationId = conversation?.conversation_id ?? "";
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [beforeCursor, setBeforeCursor] = useState<string | null>(null);
  const [hasOlder, setHasOlder] = useState(false);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const afterCursor = useRef<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);
  const readMarked = useRef<string | null>(null);

  const markDisplayedRead = useCallback((cursor: string | null) => {
    if (!conversationId || !cursor || readMarked.current === cursor) return;
    readMarked.current = cursor;
    markConversationRead(conversationId, cursor)
      .then(notifyChatChanged)
      .catch(() => {
        // Наступне polling повторить підтвердження після тимчасової помилки.
        if (readMarked.current === cursor) readMarked.current = null;
      });
  }, [conversationId]);

  const merge = useCallback((incoming: ChatMessage[]) => {
    setMessages((current) => {
      const known = new Set(current.map((item) => item.message_id));
      const fresh = incoming.filter((item) => !known.has(item.message_id));
      if (!fresh.length) return current;
      // Порядок як на бекенді: (created_at, message_id), а не порядок надходження.
      return [...current, ...fresh].sort(
        (a, b) =>
          Date.parse(a.created_at) - Date.parse(b.created_at)
          || a.created_at.localeCompare(b.created_at)
          || a.message_id.localeCompare(b.message_id),
      );
    });
  }, []);

  // Початкове завантаження й перемикання розмови.
  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;
    setMessages([]); setLoading(true); setBeforeCursor(null); setHasOlder(false); setText("");
    afterCursor.current = null; readMarked.current = null; stickToBottom.current = true;
    getMessages(conversationId)
      .then((page) => {
        if (cancelled) return;
        setMessages(page.items);
        setBeforeCursor(page.before_cursor);
        setHasOlder(page.has_more);
        afterCursor.current = page.after_cursor;
        markDisplayedRead(page.after_cursor);
      })
      .catch((requestError) => { if (!cancelled) onError(errorText(requestError)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [conversationId, markDisplayedRead, onError]);

  // Опитування нових повідомлень кожні 5 с, поки вкладка видима.
  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;
    let running = false;
    const poll = async () => {
      if (document.hidden || running || !afterCursor.current) return;
      running = true;
      try {
        const page = await getMessages(conversationId, { after: afterCursor.current });
        if (cancelled) return;
        if (page.after_cursor) afterCursor.current = page.after_cursor;
        if (page.items.length) merge(page.items);
        markDisplayedRead(page.after_cursor);
      } catch { /* наступне опитування повторить спробу */ }
      finally { running = false; }
    };
    const timer = window.setInterval(() => void poll(), THREAD_POLL_MS);
    document.addEventListener("visibilitychange", poll);
    return () => { cancelled = true; window.clearInterval(timer); document.removeEventListener("visibilitychange", poll); };
  }, [conversationId, markDisplayedRead, merge]);

  // Прокручуємо донизу, якщо користувач і так біля кінця.
  useLayoutEffect(() => {
    const node = scroller.current;
    if (node && stickToBottom.current) node.scrollTop = node.scrollHeight;
  }, [messages]);

  function onScroll() {
    const node = scroller.current;
    if (node) stickToBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 80;
  }

  async function loadOlder() {
    if (!beforeCursor) return;
    const node = scroller.current;
    const previousHeight = node?.scrollHeight ?? 0;
    try {
      const page = await getMessages(conversationId, { before: beforeCursor });
      stickToBottom.current = false;
      setMessages((current) => {
        const known = new Set(current.map((item) => item.message_id));
        return [...page.items.filter((item) => !known.has(item.message_id)), ...current];
      });
      setBeforeCursor(page.before_cursor);
      setHasOlder(page.has_more);
      requestAnimationFrame(() => { if (node) node.scrollTop = node.scrollHeight - previousHeight; });
    } catch (requestError) { onError(errorText(requestError)); }
  }

  async function send(event?: FormEvent) {
    event?.preventDefault();
    const body = text.trim();
    if (!body || sending || !conversationId) return;
    setSending(true);
    // Поле очищаємо одразу: усе, що користувач набере, поки йде запит, — вже нове повідомлення.
    const quoted = replyTo;
    setText("");
    setReplyTo(null);
    try {
      const sent = await sendChatMessage(conversationId, body, quoted?.message_id);
      stickToBottom.current = true;
      merge([sent]);
      notifyChatChanged();
    } catch (requestError) {
      // Невдача: повертаємо текст і цитату, але не затираємо новіше, що вже набрано.
      setText((current) => current || body);
      setReplyTo((current) => current ?? quoted);
      onError(errorText(requestError));
    }
    finally { setSending(false); }
  }

  // Safari/Firefox не підтримують `field-sizing: content`, тож без цього
  // Shift+Enter додає рядок, який не видно: поле лишається однорядковим.
  const composer = useRef<HTMLTextAreaElement>(null);
  const [replyTo, setReplyTo] = useState<ChatMessage | null>(null);
  const [reporting, setReporting] = useState<ChatMessage | null>(null);
  const [menu, setMenu] = useState<{ message: ChatMessage; x: number; y: number } | null>(null);
  useEffect(() => { setReplyTo(null); setReporting(null); setMenu(null); }, [conversationId]);

  // Меню повідомлення (ПКМ, довге натискання або «⋯») закривається кліком повз, Esc, прокруткою чи зміною розміру.
  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(null);
    const onKey = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") close(); };
    window.addEventListener("resize", close);
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("resize", close); window.removeEventListener("keydown", onKey); };
  }, [menu]);

  function openMenu(message: ChatMessage, x: number, y: number) {
    setMenu({ message, x, y });
  }

  async function copyText(message: ChatMessage) {
    try { await navigator.clipboard.writeText(message.body); } catch { onError("Не вдалося скопіювати текст"); }
  }

  function startReply(message: ChatMessage) {
    setReplyTo(message);
    composer.current?.focus();
  }

  function jumpTo(messageId: string) {
    const node = document.getElementById(`msg-${messageId}`);
    if (!node) return;
    node.scrollIntoView({ behavior: "smooth", block: "center" });
    node.classList.add("is-flash");
    window.setTimeout(() => node.classList.remove("is-flash"), 1400);
  }
  useLayoutEffect(() => {
    const field = composer.current;
    if (!field) return;
    field.style.height = "auto";
    field.style.height = `${Math.min(field.scrollHeight, 140)}px`;
  }, [text]);

  // Коли клавіатура змінює висоту екрана, лишаємо останні повідомлення на виду.
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const keepBottom = () => {
      const node = scroller.current;
      if (node && stickToBottom.current) node.scrollTop = node.scrollHeight;
    };
    viewport.addEventListener("resize", keepBottom);
    return () => viewport.removeEventListener("resize", keepBottom);
  }, []);

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(); }
  }

  if (!conversation) return <div className="chat-thread chat-thread-empty"><p>Оберіть розмову зі списку.</p></div>;
  return (
    <div className="chat-thread">
      <header className="chat-thread-head">
        <Link className="chat-back" to="/messages" aria-label="До списку розмов">←</Link>
        <ChatAvatar name={conversation.other.display_name} url={conversation.other.avatar_url} />
        <Link className="chat-thread-name" to={`/sellers/${conversation.other.user_id}`}>{conversation.other.display_name}</Link>
      </header>
      <div className="chat-messages" ref={scroller} onScroll={onScroll} aria-live="polite">
        {hasOlder && <button className="button button-text chat-more" type="button" onClick={() => void loadOlder()}>Показати старіші</button>}
        {loading && <p className="chat-note">Завантажуємо…</p>}
        {messages.map((message, index) => {
          const showDay = index === 0 || !sameDay(new Date(messages[index - 1].created_at), new Date(message.created_at));
          return (
            <div key={message.message_id} id={`msg-${message.message_id}`} className="chat-row">
              {showDay && <div className="chat-day"><span>{dayLabel(message.created_at)}</span></div>}
              <div
                className={`chat-bubble ${message.is_own ? "is-own" : "is-their"}`}
                onContextMenu={(event) => {
                  if (window.getSelection()?.toString()) return; // лишаємо рідне меню для виділеного тексту
                  event.preventDefault();
                  openMenu(message, event.clientX, event.clientY);
                }}
              >
                {message.reply_to && (
                  <button type="button" className="chat-quote" onClick={() => jumpTo(message.reply_to!.message_id)}>
                    <strong>{message.reply_to.is_own ? "Ви" : conversation.other.display_name}</strong>
                    <span>{message.reply_to.body}</span>
                  </button>
                )}
                {message.listing && <ListingCardView card={message.listing} />}
                <p>{message.body}</p>
                <div className="chat-meta">
                  <button type="button" className="chat-reply-btn" onClick={() => startReply(message)} aria-label="Відповісти на повідомлення">Відповісти</button>
                  <button type="button" className="chat-reply-btn chat-more-btn" aria-label="Дії з повідомленням" aria-haspopup="menu" onClick={(event) => { const box = event.currentTarget.getBoundingClientRect(); openMenu(message, box.right, box.bottom); }}>⋯</button>
                  <time dateTime={message.created_at}>{new Date(message.created_at).toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" })}</time>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {menu && createPortal(
        <>
          <button type="button" className="chat-menu-backdrop" tabIndex={-1} aria-label="Закрити меню" onClick={() => setMenu(null)} onContextMenu={(event) => { event.preventDefault(); setMenu(null); }} />
          <div className="chat-menu" role="menu" style={{ left: Math.max(8, Math.min(menu.x, window.innerWidth - 208)), top: Math.max(8, Math.min(menu.y, window.innerHeight - 156)) }}>
            <button type="button" role="menuitem" onClick={() => { startReply(menu.message); setMenu(null); }}>Відповісти</button>
            <button type="button" role="menuitem" onClick={() => { void copyText(menu.message); setMenu(null); }}>Копіювати текст</button>
            {!menu.message.is_own && <button type="button" role="menuitem" className="is-danger" onClick={() => { setReporting(menu.message); setMenu(null); }}>Поскаржитись</button>}
          </div>
        </>,
        document.body,
      )}
      {reporting && conversationId && createPortal(
        <MessageReportDialog
          conversationId={conversationId}
          messageId={reporting.message_id}
          onClose={() => setReporting(null)}
          onDone={() => { setReporting(null); onNotice("Скаргу надіслано адміністраторам"); }}
          onError={onError}
        />,
        document.body,
      )}
      {replyTo && (
        <div className="chat-reply-bar">
          <div>
            <strong>Відповідь {replyTo.is_own ? "собі" : conversation.other.display_name}</strong>
            <span>{replyTo.body}</span>
          </div>
          <button type="button" onClick={() => setReplyTo(null)} aria-label="Скасувати відповідь">×</button>
        </div>
      )}
      <form className="chat-composer" onSubmit={(event) => void send(event)}>
        <textarea ref={composer} value={text} onChange={(event) => setText(event.target.value)} onKeyDown={onKeyDown} maxLength={MESSAGE_MAX} rows={1} placeholder="Напишіть повідомлення…" aria-label="Повідомлення" />
        <button className="button button-primary" type="submit" disabled={sending || !text.trim()}>Надіслати</button>
      </form>
    </div>
  );
}

/** Сторінка «Повідомлення»: список розмов і відкрита розмова, на вузьких екранах по черзі. */
/**
 * На телефоні чат займає весь екран, як у месенджерах: сторінка не прокручується,
 * а висота й зсув беруться з visualViewport, тож екранна клавіатура піднімає поле
 * вводу (iOS Safari не зменшує layout viewport, коли з'являється клавіатура).
 */
function useChatFullscreen() {
  useEffect(() => {
    const query = window.matchMedia("(max-width: 860px)");
    const root = document.documentElement;
    const viewport = window.visualViewport;
    const timers: number[] = [];
    const clear = () => {
      root.style.removeProperty("--vv-height");
      root.style.removeProperty("--vv-top");
    };
    const sync = () => {
      if (!query.matches) {
        root.classList.remove("chat-fullscreen");
        clear();
        return;
      }
      root.classList.add("chat-fullscreen");
      if (!viewport) return;
      // iOS не зменшує layout viewport під клавіатурою і не завжди шле resize, коли її
      // закрито: якщо visual viewport знову збігся з вікном, скидаємо змінні, інакше
      // лишиться стара висота (порожня половина екрана) і зсув шапки.
      const keyboardOpen = window.innerHeight - viewport.height > 80;
      if (keyboardOpen || viewport.offsetTop > 1) {
        root.style.setProperty("--vv-height", `${viewport.height}px`);
        root.style.setProperty("--vv-top", `${viewport.offsetTop}px`);
      } else {
        clear();
      }
    };
    // Клавіатура з'являється й зникає з анімацією, тож перераховуємо кілька разів.
    const settle = () => {
      sync();
      timers.splice(0).forEach((id) => window.clearTimeout(id));
      [80, 250, 500, 900].forEach((delay) => timers.push(window.setTimeout(sync, delay)));
    };
    const onFocusOut = () => {
      settle();
      timers.push(window.setTimeout(() => window.scrollTo(0, 0), 120));
    };
    sync();
    viewport?.addEventListener("resize", settle);
    viewport?.addEventListener("scroll", sync);
    window.addEventListener("orientationchange", settle);
    document.addEventListener("focusin", settle);
    document.addEventListener("focusout", onFocusOut);
    query.addEventListener("change", sync);
    return () => {
      timers.forEach((id) => window.clearTimeout(id));
      viewport?.removeEventListener("resize", settle);
      viewport?.removeEventListener("scroll", sync);
      window.removeEventListener("orientationchange", settle);
      document.removeEventListener("focusin", settle);
      document.removeEventListener("focusout", onFocusOut);
      query.removeEventListener("change", sync);
      root.classList.remove("chat-fullscreen");
      clear();
    };
  }, []);
}

export function ChatPage({ onError, onNotice }: { onError: (message: string) => void; onNotice: (message: string) => void }) {
  const { conversationId } = useParams();
  const [items, setItems] = useState<ChatConversation[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkedId, setCheckedId] = useState<string | null>(null);
  const loadedMore = useRef(false);

  const reload = useCallback(async () => {
    try {
      const page = await getConversations();
      setItems((current) => {
        // Усе, що не потрапило в оновлену першу сторінку (і підвантажені старіші, і витіснені), лишається.
        const fresh = new Set(page.items.map((item) => item.conversation_id));
        return [...page.items, ...current.filter((item) => !fresh.has(item.conversation_id))];
      });
      if (!loadedMore.current) setCursor(page.next_cursor);
    } catch (requestError) { onError(errorText(requestError)); }
    finally { setLoading(false); }
  }, [onError]);

  useEffect(() => {
    void reload();
    const timer = window.setInterval(() => { if (!document.hidden) void reload(); }, LIST_POLL_MS);
    window.addEventListener(CHAT_CHANGED_EVENT, reload);
    return () => { window.clearInterval(timer); window.removeEventListener(CHAT_CHANGED_EVENT, reload); };
  }, [reload]);

  async function loadMore() {
    if (!cursor) return;
    try {
      const page = await getConversations(cursor);
      setItems((current) => {
        const known = new Set(current.map((item) => item.conversation_id));
        return [...current, ...page.items.filter((item) => !known.has(item.conversation_id))];
      });
      loadedMore.current = true;
      setCursor(page.next_cursor);
    } catch (requestError) { onError(errorText(requestError)); }
  }

  useChatFullscreen();
  const active = items.find((item) => item.conversation_id === conversationId) ?? null;

  // Щойно створеної розмови ще може не бути в списку: оновлюємо його і лише потім кажемо «не знайдено».
  useEffect(() => {
    if (!conversationId || loading || active) return;
    let cancelled = false;
    void (async () => {
      try {
        // Розмова може лежати за межами першої сторінки: гортаємо курсори, доки не знайдемо.
        let page = await getConversations();
        let all = [...page.items];
        let next = page.next_cursor;
        let extra = false;
        while (next && !all.some((item) => item.conversation_id === conversationId)) {
          page = await getConversations(next);
          extra = true;
          all = [...all, ...page.items];
          next = page.next_cursor;
        }
        if (cancelled) return;
        setItems((current) => {
          const known = new Set(current.map((item) => item.conversation_id));
          return [...current, ...all.filter((item) => !known.has(item.conversation_id))];
        });
        if (extra) { loadedMore.current = true; setCursor(next); }
      } catch (requestError) { if (!cancelled) onError(errorText(requestError)); }
      finally { if (!cancelled) setCheckedId(conversationId); }
    })();
    return () => { cancelled = true; };
  }, [conversationId, loading, active, onError]);
  return (
    <main className={`page-main chat-page${conversationId ? " has-thread" : ""}`}>
      <div className="chat-layout">
        <aside className="chat-sidebar" aria-label="Розмови">
          <h1><Link className="chat-back chat-home-back" to="/" aria-label="На головну">←</Link>Повідомлення</h1>
          <ConversationList conversations={items} activeId={conversationId} loading={loading} hasMore={cursor !== null} onMore={() => void loadMore()} />
        </aside>
        <section className="chat-main">
          {conversationId && !loading && !active && checkedId === conversationId ? (
            <div className="chat-thread chat-thread-empty"><p>Цю розмову не знайдено.</p><Link className="button button-light" to="/messages">До списку</Link></div>
          ) : conversationId && !active ? (
            <div className="chat-thread chat-thread-empty"><p>Завантажуємо…</p></div>
          ) : (
            <Thread key={conversationId ?? ""} conversation={active} onError={onError} onNotice={onNotice} />
          )}
        </section>
      </div>
    </main>
  );
}
