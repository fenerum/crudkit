function renderConfig(config: object) {
  document.head.innerHTML = `<script id="crudkit-config" type="application/json">${JSON.stringify(config)}</script>`;
}

async function loadAppConfig() {
  vi.resetModules();
  return (await import('../../utils/appConfig')).appConfig;
}

describe('appConfig brand color', () => {
  afterEach(() => {
    document.head.innerHTML = '';
    document.documentElement.removeAttribute('style');
    delete document.documentElement.dataset.brand;
  });

  test('sets --brand on <html> when brand_color is configured', async () => {
    renderConfig({ brand_color: '#1FB57A' });
    expect((await loadAppConfig()).brand_color).toBe('#1FB57A');
    expect(document.documentElement.style.getPropertyValue('--brand')).toBe('#1FB57A');
    expect(document.documentElement.dataset.brand).toBe('');
  });

  test('leaves the default palette alone without brand_color', async () => {
    renderConfig({ app_name: 'Acme' });
    expect((await loadAppConfig()).brand_color).toBeNull();
    expect(document.documentElement.style.getPropertyValue('--brand')).toBe('');
    expect(document.documentElement.dataset.brand).toBeUndefined();
  });
});
