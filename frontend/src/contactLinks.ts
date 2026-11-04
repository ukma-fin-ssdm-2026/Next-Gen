const TELEGRAM_PATTERN = /^@[A-Za-z0-9_]{3,}$/;
const PHONE_PATTERN = /^\+?[0-9][0-9\s()-]{6,}$/;

/**
 * Перевіряє адресу без регулярного виразу з вкладеними квантифікаторами:
 * рівно один «@», обидві частини непорожні, у домені є крапка не на краю.
 */
export function isEmail(value: string): boolean {
  if (/\s/.test(value)) return false;
  const parts = value.split("@");
  if (parts.length !== 2) return false;
  const [local, domain] = parts;
  if (!local || !domain) return false;
  const dot = domain.indexOf(".", 1);
  return dot !== -1 && dot < domain.length - 1;
}

/** Перетворює контакт на посилання: пошта, Telegram або телефон; інакше `null`. */
export function contactHref(contact: string): string | null {
  const value = contact.trim();
  if (isEmail(value)) return `mailto:${value}`;
  if (TELEGRAM_PATTERN.test(value)) return `https://t.me/${value.slice(1)}`;
  if (PHONE_PATTERN.test(value)) return `tel:${value.replace(/[^\d+]/g, "")}`;
  return null;
}
