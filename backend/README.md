# Lucent backend

The API uses PostgreSQL and Alembic for schema changes.

From `backend/`, apply migrations with:

```bash
venv/bin/alembic upgrade head
```

For an existing development database created before Alembic, mark the existing
base schema and then apply the passage-column migration without recreating data:

```bash
venv/bin/alembic stamp 0001_initial_schema
venv/bin/alembic upgrade head
```

Use `venv/bin/alembic current` to inspect the installed revision. New empty
databases should run only `upgrade head`.
