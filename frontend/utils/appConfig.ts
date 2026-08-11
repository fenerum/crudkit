/**
 * Runtime app configuration, rendered into index.html by the Django backend
 * (see CRUDKIT_FRONTEND_CONFIG). The Vite dev server serves the template
 * unrendered, so parsing fails there and the generic defaults apply.
 */

export interface AppConfig {
  app_name: string;
  org_name: string;
  logo_url: string | null;
  auth_mode: 'password' | 'saml';
  storage_prefix: string;
  conversation_link_pattern: string;
}

const defaults: AppConfig = {
  app_name: 'CrudKit',
  org_name: 'CrudKit',
  logo_url: null,
  auth_mode: 'password',
  storage_prefix: 'crudkit',
  conversation_link_pattern: 'deal|opportunity|case',
};

function load(): AppConfig {
  try {
    const el = document.getElementById('crudkit-config');
    if (!el) return defaults;
    const parsed = JSON.parse(el.textContent || '');
    if (parsed && typeof parsed === 'object') {
      return { ...defaults, ...parsed };
    }
  } catch {
    // Unrendered template (dev) or malformed JSON — use defaults.
  }
  return defaults;
}

export const appConfig: AppConfig = load();
