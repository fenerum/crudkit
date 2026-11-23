import { visibleView } from '../../utils/visibleView';

const metadata = { fields: { name: {}, status: {}, owner: {} } };

describe('visibleView', () => {
  test('keeps a view whose fields are all visible as it is', () => {
    const view = { layout: 'list', fields: ['name', 'status'], group_by: 'status' };
    expect(visibleView(view, metadata)).toBe(view);
  });

  test('drops columns the person may not see', () => {
    const view = { layout: 'list', fields: ['name', 'special_terms', 'status'] };
    expect(visibleView(view, metadata).fields).toEqual(['name', 'status']);
  });

  test('falls back to a list when a board groups by a hidden field', () => {
    const view = { layout: 'kanban', fields: ['name'], group_by: 'special_terms' };
    expect(visibleView(view, metadata)).toMatchObject({ layout: 'list', group_by: null });
  });

  test('drops a total over a hidden field', () => {
    const view = { layout: 'list', fields: ['name'], aggregate_by: 'amount', aggregate_type: 'sum' };
    expect(visibleView(view, metadata)).toMatchObject({ aggregate_by: null, aggregate_type: null });
  });

  test('falls back to a list when a quadrant loses an axis', () => {
    const view = { layout: 'quadrant', fields: ['name', 'amount'] };
    expect(visibleView(view, metadata).layout).toBe('list');
  });

  test('follows related paths to their first field', () => {
    const view = { layout: 'list', fields: ['name'], group_by: 'owner__username' };
    expect(visibleView(view, metadata)).toBe(view);
  });
});
