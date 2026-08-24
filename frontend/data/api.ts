export class ValidationError extends Error {
  errors: Record<string, any>;
  response?: Response;
  constructor(message: string, errors: Record<string, any>, response?: Response) {
    super(message);
    this.errors = errors;
    this.response = response;
  }
}

// `kind` lets the fetch wrapper tell apart "the refresh token is dead, sign
// the user out" from "we couldn't reach the refresh endpoint, retry later".
// Without this distinction, transient backend hiccups would clear the tokens.
export class TokenRefreshError extends Error {
  kind: 'rejected' | 'transient';
  constructor(message: string, kind: 'rejected' | 'transient') {
    super(message);
    this.kind = kind;
  }
}

const isDevelopment = (): boolean => {
  if (typeof window === 'undefined') return import.meta.env?.DEV ?? false;
  return (
    import.meta.env?.DEV ||
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1'
  );
};

const getDefaultBaseUrl = (): string => {
  if (typeof window === 'undefined') return '';
  if (!isDevelopment()) return window.location.origin;

  // In dev, the Vite proxy sends /api, /ws, /saml2, /static, /media to Django.
  // Using a relative base lets fetch() and WebSocket() ride the same origin.
  return '';
};

export default class CrudKitAPIClient {
  baseUrl: string;
  clientId: string = 'CrudKitAPIClient';

  constructor(baseUrl: string = '') {
    this.baseUrl = baseUrl ? baseUrl : getDefaultBaseUrl();
  }

  async login(username: string, password: string) {
    const response = await fetch(`${this.baseUrl}/api/v1/token/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Client-Id': this.clientId,
      },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const errorData = await response.text();
      throw new Error(`Login failed: ${errorData}`);
    }

    const data = await response.json();
    this.storeTokens(data.access, data.refresh);
    return data.user;
  }

  async refreshToken() {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) throw new TokenRefreshError('No refresh token available', 'rejected');

    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}/api/v1/token/refresh/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Client-Id': this.clientId,
        },
        body: JSON.stringify({ refresh: refreshToken }),
      });
    } catch (networkError) {
      throw new TokenRefreshError('Token refresh request failed: network error', 'transient');
    }

    if (response.status === 401 || response.status === 403) {
      this.clearTokens();
      throw new TokenRefreshError('Token refresh failed: refresh token rejected', 'rejected');
    }

    if (!response.ok) {
      throw new TokenRefreshError(
        `Token refresh failed: server returned ${response.status}`,
        'transient',
      );
    }

    const data = await response.json();
    this.storeAccessToken(data.access);
    return data.access;
  }

  async logout() {
    const accessToken = this.getAccessToken();
    const refreshToken = this.getRefreshToken();
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    try {
      await fetch(`${this.baseUrl}/api/v1/logout/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'Client-Id': this.clientId,
          ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({ refresh: refreshToken }),
      });
    } catch (error) {
      if (isDevelopment()) console.warn('Server logout failed; local credentials were cleared', error);
    } finally {
      this.clearTokens();
    }
  }

  storeTokens(accessToken: string, refreshToken: string) {
    localStorage.setItem('accessToken', accessToken);
    localStorage.setItem('refreshToken', refreshToken);
  }

  storeAccessToken(accessToken: string) {
    localStorage.setItem('accessToken', accessToken);
  }

  getAccessToken(): string | null {
    return localStorage.getItem('accessToken');
  }

  getRefreshToken(): string | null {
    return localStorage.getItem('refreshToken');
  }

  clearTokens() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
  }

  isAuthenticated(): boolean {
    return !!this.getAccessToken();
  }

  cleanObject(metadata: any, obj: Record<string, any>) {
    const booleanFieldsExpected = Object.entries(metadata.fields)
      .filter(([, field_object]: [string, any]) => field_object.type === 'BooleanField' && field_object.editable)
      .map(([field_name]) => field_name);

    for (const field_name of booleanFieldsExpected) {
      if (!obj[field_name]) {
        obj[field_name] = false;
      }
    }

    for (const [key, value] of Object.entries(obj)) {
      const fieldMeta = metadata.fields[key];
      if (!fieldMeta) {
        // Drop anything the model doesn't expose as a field. Read-only extras
        // like `label` / `object_images` come back from the detail endpoint
        // and we don't want to echo them in the submission payload.
        delete obj[key];
        continue;
      }

      if (
        (fieldMeta.type === 'ForeignKey' || fieldMeta.type === 'OneToOneField') &&
        value && typeof value === 'object' && (value as any).id !== undefined
      ) {
        obj[key] = (value as any).id;
      } else if (
        fieldMeta.type !== 'TextField' &&
        fieldMeta.type !== 'CharField' &&
        value === ''
      ) {
        obj[key] = null;
      }

      if (fieldMeta.type === 'JSONField' && value !== '' && value !== null) {
        // Only parse if the field is still a raw string from the textarea.
        // If a prior step (form prefill, detail fetch) already handed us an
        // object/array, leave it alone.
        if (typeof value === 'string') {
          try {
            obj[key] = JSON.parse(value);
          } catch (error) {
            throw new ValidationError('Invalid JSON', { [key]: 'Invalid JSON - ' + error });
          }
        }
      }

      if (fieldMeta.type === 'BooleanField') {
        obj[key] = value === 'on' || value === true;
      }

      if (fieldMeta.type === 'ImageField') {
        if (value === '' || (typeof value === 'string' && !value.startsWith('data:'))) {
          delete obj[key];
        }
      }
    }
    return obj;
  }

  async fetch(url: string, options: Record<string, any> = {}) {
    if (!options.headers) options.headers = {};

    options.headers['X-CSRFToken'] =
      document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || null;
    options.credentials = 'include';

    const token = this.getAccessToken();
    if (token) options.headers['Authorization'] = `Bearer ${token}`;

    const fullUrl = `${this.baseUrl}/${url}`;
    if (isDevelopment()) console.log(`API request to: ${fullUrl}`);

    let response = await fetch(fullUrl, {
      headers: Object.assign(options.headers, {
        'Client-Id': this.clientId,
        Accept: 'application/json',
        charset: 'utf-8',
      }),
      ...options,
    });

    // Only try to refresh if we actually have a refresh token to use. Hitting
    // a 401 with no tokens at all just means the user isn't signed in — there's
    // nothing to refresh, so skipping avoids a noisy "No refresh token
    // available" error in the console.
    if (response.status === 401 && this.getRefreshToken()) {
      try {
        const newToken = await this.refreshToken();
        options.headers['Authorization'] = `Bearer ${newToken}`;
        if (isDevelopment()) console.log(`Retrying API request to: ${fullUrl} after token refresh`);
        response = await fetch(fullUrl, {
          headers: Object.assign(options.headers, {
            'Client-Id': this.clientId,
            Accept: 'application/json',
            charset: 'utf-8',
          }),
          ...options,
        });
      } catch (error) {
        console.error('Token refresh failed', error);
        // For transient refresh failures (network, 5xx) surface a non-401 error
        // so callers like `AuthContext` keep the stored tokens — the user can
        // retry once the backend is reachable again. Only let the original 401
        // propagate when the refresh token itself was rejected.
        if (error instanceof TokenRefreshError && error.kind === 'transient') {
          const transient: any = new Error(error.message);
          transient.statusCode = 0;
          transient.transient = true;
          throw transient;
        }
      }
    }

    if (response.status === 400 && response.headers.get('Content-Type')?.includes('application/json')) {
      const error = await response.json();
      console.log('API returned validation error:', error);
      if (error && error.errors && Array.isArray(error.errors)) {
        const validationError = new ValidationError('Invalid Request', error, response);
        validationError.errors = error.errors;
        throw validationError;
      } else {
        throw new ValidationError('Invalid Request', error, response);
      }
    }

    if (!response.ok) {
      const errorText = await response.text();
      let errorData: any = null;
      try {
        errorData = JSON.parse(errorText);
      } catch {
        // not JSON
      }
      const error: any = new Error('Failed to load data from server\n' + response.statusText);
      error.statusCode = response.status;
      error.statusText = response.statusText;
      error.errorData = errorData;
      error.errorText = errorText;
      throw error;
    }

    return response.clone();
  }

  async httpGet(relativeURL: string, querystring: Record<string, any> = {}) {
    return querystring
      ? await this.fetch(`${relativeURL}?${new URLSearchParams(querystring)}`)
      : await this.fetch(`${relativeURL}`);
  }

  async httpPost(relativeURL: string, data: Record<string, any> = {}, querystring: Record<string, any> = {}) {
    return await this.fetch(`${relativeURL}?${new URLSearchParams(querystring)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  }

  async httpPut(relativeURL: string, data: Record<string, any>) {
    return await this.fetch(relativeURL, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  }

  async httpPatch(relativeURL: string, data: Record<string, any>) {
    return await this.fetch(relativeURL, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  }

  async httpDelete(relativeURL: string) {
    return await this.fetch(relativeURL, { method: 'DELETE' });
  }

  async httpOptions(relativeURL: string) {
    return await this.fetch(relativeURL, { method: 'OPTIONS' });
  }

  async list(modelName: string, filters: Record<string, any> = {}) {
    for (const key in filters) {
      if (typeof filters[key] === 'boolean') {
        filters[key] = filters[key] ? 'True' : 'False';
      }
    }
    const response = await this.httpGet(`api/v1/${modelName}/`, filters);
    const data = await response.json();
    if (data && data.results !== undefined) {
      return {
        results: data.results,
        count: data.count,
        next: data.next,
        previous: data.previous,
        page_size: data.page_size,
        current_page: data.current_page,
        total_pages: data.total_pages,
        isPaginated: true,
      };
    }
    return data;
  }

  async getNextPage(nextUrl: string) {
    if (!nextUrl) return null;
    const urlObj = new URL(nextUrl);
    const pathWithQuery = urlObj.pathname + urlObj.search;
    const response = await this.fetch(pathWithQuery.substring(1));
    return await response.json();
  }

  async getPreviousPage(previousUrl: string) {
    if (!previousUrl) return null;
    const urlObj = new URL(previousUrl);
    const pathWithQuery = urlObj.pathname + urlObj.search;
    const response = await this.fetch(pathWithQuery.substring(1));
    return await response.json();
  }

  async retrieve(modelName: string, id: string) {
    return await this.httpGet(`api/v1/${modelName}/${id}/`).then((r) => r.json());
  }

  async create(modelName: string, data: Record<string, any>, prefills: Record<string, any>) {
    return await this.httpPost(`api/v1/${modelName}/`, data, prefills).then((r) => r.json());
  }

  async update(modelName: string, id: string, data: Record<string, any>) {
    return await this.httpPut(`api/v1/${modelName}/${id}/`, data).then((r) => r.json());
  }

  async partialUpdate(modelName: string, id: string, data: Record<string, any>) {
    return await this.httpPatch(`api/v1/${modelName}/${id}/`, data).then((r) => r.json());
  }

  async delete(modelName: string, id: string) {
    return await this.httpDelete(`api/v1/${modelName}/${id}/`);
  }

  async metadata(modelName: string) {
    return await this.httpGet(`api/v1/${modelName}/metadata/`).then((r) => r.json());
  }

  async initial(modelName: string, prefills: Record<string, any> = {}) {
    const response = await this.httpGet(`api/v1/${modelName}/initial/`, prefills);
    const data = await response.json();
    return data.fields || {};
  }

  async action(modelName: string, id: string, action: string) {
    return await this.httpPost(`api/v1/${modelName}/${id}/action/`, { action }).then((r) => r.json());
  }

  async merge(modelName: string, id: string, data: Record<string, any>) {
    try {
      const response = await this.httpPost(`api/v1/${modelName}/${id}/merge/`, data);
      return await response.json();
    } catch (error: any) {
      console.error('Merge operation failed:', error);
      if (error.errorData) {
        console.log('Server returned error data:', error.errorData);
        if (error.errorData.errors) {
          error.serverErrors = error.errorData.errors;
        }
      }
      throw error;
    }
  }

  async search(query: string = '') {
    return await this.httpGet(`api/v1/search/`, { q: query }).then((r) => r.json());
  }
}

const apiClient = new CrudKitAPIClient();

export async function fetchMetadata(modelType: string) {
  return apiClient.metadata(modelType);
}

export async function fetchObject(modelType: string, id: string) {
  return apiClient.retrieve(modelType, id);
}

export async function fetchObjects(modelType: string, filters?: Record<string, any>) {
  return apiClient.list(modelType, filters || {});
}

export async function fetchNextPage(nextUrl: string) {
  return apiClient.getNextPage(nextUrl);
}

export async function fetchPreviousPage(previousUrl: string) {
  return apiClient.getPreviousPage(previousUrl);
}

export async function createObject(
  modelType: string,
  data: Record<string, any>,
  prefills?: Record<string, any>,
) {
  return apiClient.create(modelType, data, prefills || {});
}

export async function updateObject(modelType: string, id: string, data: Record<string, any>) {
  return apiClient.update(modelType, id, data);
}

export async function deleteObject(modelType: string, id: string) {
  return apiClient.delete(modelType, id);
}

export async function mergeObjects(modelType: string, data: Record<string, any>) {
  const id = Array.isArray(data.merge) && data.merge.length > 0 ? data.merge[0] : undefined;
  if (!id) throw new Error('No objects specified for merging');

  try {
    return await apiClient.merge(modelType, id, data);
  } catch (error: any) {
    if (error.serverErrors) {
      const enhancedError: any = new Error(error.message || 'Merge operation failed');
      enhancedError.serverErrors = error.serverErrors;
      throw enhancedError;
    }
    throw error;
  }
}

export async function performAction(modelType: string, id: string, action: string) {
  return apiClient.action(modelType, id, action);
}

export async function performSearch(query: string) {
  return apiClient.search(query);
}

export async function login(username: string, password: string) {
  return apiClient.login(username, password);
}

export async function logout() {
  return apiClient.logout();
}

export async function isAuthenticated() {
  return apiClient.isAuthenticated();
}

export function getAccessToken(): string | null {
  return apiClient.getAccessToken();
}
