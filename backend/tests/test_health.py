def test_health(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "backend is alive"}


def test_liveness_does_not_depend_on_database(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_requires_database_at_migration_head(client, monkeypatch):
    import app.main as main_module

    class Result:
        def scalars(self):
            return iter(["expected-head"])

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, statement):
            return Result()

    monkeypatch.setattr(main_module, "engine", type("ReadyEngine", (), {"connect": lambda self: Connection()})())
    monkeypatch.setattr(main_module, "_expected_database_revisions", lambda: frozenset({"expected-head"}))
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_rejects_migration_mismatch(client, monkeypatch):
    import app.main as main_module

    class Result:
        def scalars(self):
            return iter(["old-head"])

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, statement):
            return Result()

    monkeypatch.setattr(main_module, "engine", type("StaleEngine", (), {"connect": lambda self: Connection()})())
    monkeypatch.setattr(main_module, "_expected_database_revisions", lambda: frozenset({"expected-head"}))

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "component": "database", "reason": "migration_mismatch"}


def test_readiness_fails_closed_without_exposing_database_error(client, monkeypatch):
    import app.main as main_module

    class BrokenEngine:
        def connect(self):
            raise RuntimeError("postgresql://secret-user:secret-password@private-host/student-data")

    monkeypatch.setattr(main_module, "engine", BrokenEngine())
    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "component": "database", "reason": "unavailable"}
    assert "secret-password" not in response.text


def test_readiness_reports_unreadable_migrations_separately_from_database(client, monkeypatch):
    """A packaging fault must not be reported to operators as a database outage."""
    import app.main as main_module

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def execute(self, statement):
            raise AssertionError("the database must not be consulted when migrations are unreadable")

    def broken_revisions():
        raise FileNotFoundError("alembic.ini")

    monkeypatch.setattr(main_module, "engine", type("Engine", (), {"connect": lambda self: Connection()})())
    monkeypatch.setattr(main_module, "_expected_database_revisions", broken_revisions)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "component": "migrations", "reason": "unreadable"}
    assert "alembic.ini" not in response.text
