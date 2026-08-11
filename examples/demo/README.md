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
