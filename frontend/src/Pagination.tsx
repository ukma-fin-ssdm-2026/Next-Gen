import { useEffect, useMemo, useState } from "react";

/** Номери сторінок із пропусками: 1 … 4 5 [6] 7 8 … 20. */
function pageNumbers(page: number, totalPages: number): Array<number | "gap"> {
  const wanted = new Set([1, totalPages, page - 1, page, page + 1]);
  const sorted = [...wanted].filter((n) => n >= 1 && n <= totalPages).sort((a, b) => a - b);
  const result: Array<number | "gap"> = [];
  sorted.forEach((n, index) => {
    if (index > 0 && n - sorted[index - 1] > 1) result.push("gap");
    result.push(n);
  });
  return result;
}

export function Pagination({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (page: number) => void }) {
  if (totalPages <= 1) return null;
  return (
    <nav className="pagination" aria-label="Сторінки">
      <button type="button" className="page-btn" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Попередня сторінка">‹</button>
      {pageNumbers(page, totalPages).map((item, index) =>
        item === "gap" ? (
          <span key={`gap-${index}`} className="page-gap" aria-hidden="true">…</span>
        ) : (
          <button key={item} type="button" className={item === page ? "page-btn is-active" : "page-btn"} aria-current={item === page ? "page" : undefined} onClick={() => onChange(item)}>{item}</button>
        ),
      )}
      <button type="button" className="page-btn" disabled={page >= totalPages} onClick={() => onChange(page + 1)} aria-label="Наступна сторінка">›</button>
    </nav>
  );
}

/** Розбиває вже завантажений список на сторінки; `resetKey` повертає на першу сторінку. */
export function usePaged<T>(items: T[], pageSize: number, resetKey = "") {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  useEffect(() => setPage(1), [resetKey]);
  const current = Math.min(page, totalPages);
  const slice = useMemo(() => items.slice((current - 1) * pageSize, current * pageSize), [items, current, pageSize]);
  return { slice, page: current, totalPages, setPage };
}
