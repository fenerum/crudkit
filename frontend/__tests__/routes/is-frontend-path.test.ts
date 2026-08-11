import { isFrontendPath } from '../../src/routes/is-frontend-path';

describe('isFrontendPath', () => {
  describe('frontend paths', () => {
    test.each([
      ['/'],
      ['/login'],
      ['/login/'],
      ['/inbox'],
      ['/all-objects'],
      ['/profile'],
      ['/search'],
      ['/COM'],
      ['/COM/'],
      ['/OPP2109'],
      ['/COM/create'],
      ['/COM/edit'],
      ['/COM/delete'],
      ['/COM/merge'],
      ['/COM123/edit'],
      ['/COM/VIW/my-view'],
      ['/COM123/VIW/kanban'],
    ])('returns true for %s', (path) => {
      expect(isFrontendPath(path)).toBe(true);
    });
  });

  describe('backend paths', () => {
    test.each([
      ['/orderform/offer/OPP2109/'],
      ['/admin/'],
      ['/admin/auth/user/'],
      ['/api/v1/foo'],
      ['/saml2/login/'],
      ['/accounts/login/'],
      ['/media/uploads/file.pdf'],
      ['/static/css/app.css'],
      ['/chat/'],
      ['/survey/abc'],
    ])('returns false for %s', (path) => {
      expect(isFrontendPath(path)).toBe(false);
    });
  });

  describe('query and hash handling', () => {
    test('ignores query string', () => {
      expect(isFrontendPath('/OPP123?tab=properties')).toBe(true);
    });

    test('ignores hash fragment', () => {
      expect(isFrontendPath('/OPP123#section')).toBe(true);
    });

    test('ignores both query and hash', () => {
      expect(isFrontendPath('/COM/edit?id=1#focus')).toBe(true);
    });

    test('still rejects backend paths with query', () => {
      expect(isFrontendPath('/orderform/offer/OPP2109/?download=1')).toBe(false);
    });
  });

  describe('invalid segments', () => {
    test('rejects lowercase segment', () => {
      expect(isFrontendPath('/com123')).toBe(false);
    });

    test('rejects segment longer than 3 letters', () => {
      expect(isFrontendPath('/COMPANY')).toBe(false);
    });

    test('rejects segment shorter than 3 letters', () => {
      expect(isFrontendPath('/CO')).toBe(false);
    });

    test('rejects unknown sub-action', () => {
      expect(isFrontendPath('/COM/bogus')).toBe(false);
    });

    test('rejects VIW without a view id', () => {
      expect(isFrontendPath('/COM/VIW/')).toBe(false);
    });
  });
});
