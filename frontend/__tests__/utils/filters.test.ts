import { fieldKind, fkCkId, parseFilters, validateFilter } from '../../utils/filters';

const fields = {
  name: { type: 'CharField' },
  status: { type: 'CharField', choices: [['active', 'Active'], ['churned', 'Churned']] as [string, string][] },
  vip: { type: 'BooleanField' },
  pages: { type: 'PositiveIntegerField' },
  due: { type: 'DateField' },
  created_at: { type: 'DateTimeField' },
  topic: { type: 'ForeignKey', related_model: 'Topic', related_model_type: 'TOP' },
  owner: { type: 'ForeignKey', related_model: 'User', related_model_type: null },
};

describe('fieldKind', () => {
  test('maps field metadata to an editor kind', () => {
    expect(fieldKind(fields.status)).toBe('choice');
    expect(fieldKind(fields.vip)).toBe('boolean');
    expect(fieldKind(fields.pages)).toBe('number');
    expect(fieldKind(fields.due)).toBe('date');
    expect(fieldKind(fields.created_at)).toBe('datetime');
    expect(fieldKind(fields.topic)).toBe('fk');
    expect(fieldKind(fields.owner)).toBe('number');
    expect(fieldKind(fields.name)).toBe('text');
    expect(fieldKind(undefined)).toBe('path');
  });
});

describe('parseFilters', () => {
  test('reads arrays, JSON strings and empty values', () => {
    expect(parseFilters(null)).toEqual({ rows: [] });
    expect(parseFilters('')).toEqual({ rows: [] });
    expect(parseFilters('[["name", "=", "x"]]')).toEqual({ rows: [['name', '=', 'x']] });
  });

  test('hands back unreadable values as raw text', () => {
    expect(parseFilters('[["name"')).toEqual({ raw: '[["name"' });
    expect(parseFilters({ name: 'x' })).toEqual({ raw: '{\n  "name": "x"\n}' });
  });
});

describe('fkCkId', () => {
  test('accepts CK-IDs and plain pks', () => {
    expect(fkCkId('TOP3', 'TOP')).toBe('TOP3');
    expect(fkCkId(3, 'TOP')).toBe('TOP3');
    expect(fkCkId('abc', 'TOP')).toBeNull();
  });
});

describe('validateFilter', () => {
  test.each([
    [['status', '=', 'active']],
    [['status', '!=', null]],
    [['vip', '=', false]],
    [['pages', '>=', 100]],
    [['due', '<', '2026-01-31']],
    [['created_at', '>', '2026-01-31T10:00']],
    [['topic', '=', 'TOP3']],
    [['owner', '=', '${user}']],
    [['topic__name', '=', 'Billing']],
  ])('%j is valid', (row) => {
    expect(validateFilter(row, fields)).toBeNull();
  });

  test.each([
    ['oops', 'Not a [field, comparator, value] filter'],
    [['name', '='], 'Not a [field, comparator, value] filter'],
    [['', '=', null], 'Pick a field'],
    [['colour', '=', 'red'], 'Unknown field "colour"'],
    [['name', '~', 'x'], 'Unknown comparator "~"'],
    [['status', '=', 'archived'], '"archived" is not one of the choices'],
    [['vip', '=', 'yes'], '"yes" is not yes or no'],
    [['pages', '>=', 'lots'], '"lots" is not a number'],
    [['due', '=', '31/01/2026'], '"31/01/2026" is not a date'],
    [['topic', '=', 'Billing'], '"Billing" is not a record ID'],
  ])('%j is invalid', (row, message) => {
    expect(validateFilter(row, fields)).toContain(message);
  });
});
