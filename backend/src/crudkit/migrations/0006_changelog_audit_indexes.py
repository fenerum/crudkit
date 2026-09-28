"""
The change log indexes 0004 declares, built outside a transaction and, on
PostgreSQL, CONCURRENTLY: a plain CREATE INDEX locks out inserts to the change
log, and nearly every write inserts into it. Databases that got the indexes
from an earlier 0004 already have them, hence IF NOT EXISTS.
"""

from django.db import migrations

INDEXES = [
    # (name or None for Django's db_index name, columns)
    (None, ["change_set"]),
    (None, ["revert_of"]),
    ("crudkit_cha_related_df5fbc_idx", ["related_content_type_id", "related_object_id"]),
]


def _invalid_indexes(connection) -> set[str]:
    """PostgreSQL leaves an INVALID index behind when a concurrent build fails."""
    if connection.vendor != "postgresql":
        return set()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid WHERE NOT i.indisvalid"
        )
        return {row[0] for row in cursor.fetchall()}


def create_indexes(apps, schema_editor):
    table = apps.get_model("crudkit", "ChangeLog")._meta.db_table
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        existing = set(connection.introspection.get_constraints(cursor, table))
    invalid = _invalid_indexes(connection)
    quote = schema_editor.quote_name
    concurrently = "CONCURRENTLY " if connection.vendor == "postgresql" else ""
    for name, columns in INDEXES:
        # Same name Django gives a db_index, so later migrations can find it.
        name = name or schema_editor._create_index_name(table, columns, suffix="")
        if name in invalid:
            schema_editor.execute(f"DROP INDEX {concurrently}{quote(name)}")
        elif name in existing:
            continue
        schema_editor.execute(
            f"CREATE INDEX {concurrently}{quote(name)} ON {quote(table)} ({', '.join(quote(c) for c in columns)})"
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("crudkit", "0005_aicontext"),
    ]

    operations = [
        migrations.RunPython(create_indexes, migrations.RunPython.noop),
    ]
