def test_legacy_entrypoint_aliases_authoritative_application():
    import main as compatibility_entrypoint
    from app.main import app

    assert compatibility_entrypoint.app is app
