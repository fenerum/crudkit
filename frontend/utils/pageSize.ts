// Remembers the user's last page-size choice across pages and reloads.
// Inlines and full lists are stored separately since they're usually wanted
// at different densities.
export type PageSizeScope = 'inline' | 'list';

const COOKIE_NAMES: Record<PageSizeScope, string> = {
  inline: 'crudkit_inline_page_size',
  list: 'crudkit_list_page_size',
};

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

export function getStoredPageSize(scope: PageSizeScope): number | null {
  const name = COOKIE_NAMES[scope];
  const entry = document.cookie.split('; ').find((c) => c.startsWith(`${name}=`));
  if (!entry) return null;
  const size = parseInt(entry.slice(name.length + 1), 10);
  return Number.isInteger(size) && size > 0 ? size : null;
}

export function storePageSize(scope: PageSizeScope, size: number): void {
  document.cookie = `${COOKIE_NAMES[scope]}=${size}; path=/; max-age=${ONE_YEAR_SECONDS}; SameSite=Lax`;
}
