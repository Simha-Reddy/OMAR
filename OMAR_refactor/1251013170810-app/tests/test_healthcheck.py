from app import create_app


def test_healthz_endpoint_returns_ok(monkeypatch):
    """Ensure the container health endpoint is reachable."""
    # Force fakeredis to simplify unit tests
    monkeypatch.setenv("USE_FAKEREDIS", "1")

    app = create_app()
    app.config.update(TESTING=True)

    client = app.test_client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
