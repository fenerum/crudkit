import { getStoredPageSize, storePageSize } from '../../utils/pageSize';

describe('page size cookies', () => {
  beforeEach(() => {
    document.cookie = 'crudkit_inline_page_size=; max-age=0; path=/';
    document.cookie = 'crudkit_list_page_size=; max-age=0; path=/';
  });

  test('returns null when nothing is stored', () => {
    expect(getStoredPageSize('inline')).toBeNull();
    expect(getStoredPageSize('list')).toBeNull();
  });

  test('round-trips per scope independently', () => {
    storePageSize('inline', 25);
    storePageSize('list', 50);
    expect(getStoredPageSize('inline')).toBe(25);
    expect(getStoredPageSize('list')).toBe(50);
  });

  test('ignores invalid values', () => {
    document.cookie = 'crudkit_list_page_size=abc; path=/';
    expect(getStoredPageSize('list')).toBeNull();
    document.cookie = 'crudkit_list_page_size=0; path=/';
    expect(getStoredPageSize('list')).toBeNull();
  });
});
