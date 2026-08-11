# CrudKit demo project

A from-scratch Django project on `django-crudkit`: two models (`Author` AUT,
`Book` BOK) and the generic REST API — no per-model serializers, viewsets or
routes.

```
uv sync
uv run manage.py migrate
uv run manage.py createsuperuser
uv run manage.py runserver
```

Then explore:

- `POST /api/v1/token/` — JWT login
- `GET /api/v1/BOK/` — list books
- `GET /api/v1/BOK/metadata/` — the model schema the frontend renders from
- `POST /api/v1/BOK/` — create (`{"title": "...", "author": "AUT1"}`)
- `GET /api/v1/search/?_q=...` — global search

## The bundled web UI

The demo also wires up `crudkit_frontend`, which serves the CrudKit SPA at
`/`. Build the frontend once, then `runserver` serves the full UI:

```
cd ../../frontend
npm ci
npm run build     # emits assets + index.html into backend/src/crudkit_frontend/
cd ../examples/demo
uv run manage.py runserver
```

Then open http://localhost:8000/ and log in with your superuser. The app name
comes from the `CRUDKIT_FRONTEND_CONFIG` setting ("CrudKit Demo" here).
