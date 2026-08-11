# CrudKit frontend

The metadata-driven web SPA for [django-crudkit](../backend/). Vite + React 18
+ TypeScript + Tailwind, talking to the generic CrudKit REST API at `/api/v1/`.

## Development

```bash
npm install
npm run dev      # Vite dev server on :8100, proxies /api → http://localhost:8000
npm run build    # production build → ../backend/src/crudkit_frontend/
npm test         # vitest
npm run lint
```

The dev server proxies `/api`, `/saml2`, `/static`, `/media`, and `/ws` to
`http://localhost:${BACKEND_PORT:-8000}` so it talks to any locally-running
CrudKit-based Django backend (set `BACKEND_PORT` or `DEV_PORT` to change it).

Branding (app name, logo, org name) is not compiled in: it is read at runtime
from the `<script id="crudkit-config" type="application/json">` tag that the
`crudkit_frontend.context_processors.crudkit_config` context processor renders
from the `CRUDKIT_FRONTEND_CONFIG` Django setting (see `utils/appConfig.ts`
for the defaults used in dev).

## Routing

React Router v7 in SPA mode. Routes are declared in `src/App.tsx`. The dynamic
`:segment` param matches both list-style codes (`CAS`) and detail-style codes
(`CAS1`); `src/routes/segment-index.tsx` dispatches between `List` and
`Detail` based on the format.

## Form fields

Forms use `react-hook-form` end-to-end. `components/Fields/BaseField.tsx` is
the integration point — every concrete field (CharField, DateField, etc.)
wraps it. `FormContainer` provides the `FormProvider` context. For one-off
fields, use `StandaloneFieldWrapper` from `context/FormContext.jsx`.

## Production

`npm run build` emits hashed assets into
`../backend/src/crudkit_frontend/static/crudkit_frontend/` and the SPA shell
into `../backend/src/crudkit_frontend/templates/crudkit_frontend/index.html`,
so the built SPA ships inside the `django-crudkit` wheel and is served by the
`crudkit_frontend` Django app. The shell is rendered as a Django template; the
`{{ csrf_token }}` and `{{ crudkit_config_json }}` placeholders survive the
Vite build untouched (asserted by `scripts/postbuild.mjs`).

Sourcemaps are not emitted by default (the `.js.map` is ~6.6 MB and would
ship in the wheel). To debug a production bundle, build with:

```bash
CRUDKIT_SOURCEMAP=1 npm run build
```
