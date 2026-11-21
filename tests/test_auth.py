from tests.conftest import make_user


def test_register_and_login(client):
    headers = make_user(client)
    assert headers["Authorization"].startswith("Bearer ")


def test_duplicate_email_is_409(client):
    make_user(client)
    r = client.post(
        "/auth/register", json={"email": "ALICE@example.com", "password": "password123"}
    )
    assert r.status_code == 409


def test_wrong_password_is_401(client):
    make_user(client)
    r = client.post("/auth/login", json={"email": "alice@example.com", "password": "nope-nope"})
    assert r.status_code == 401


def test_short_password_rejected(client):
    r = client.post("/auth/register", json={"email": "bob@example.com", "password": "short"})
    assert r.status_code == 422


def test_protected_route_requires_token(client):
    r = client.post("/urls", json={"original_url": "https://example.com"})
    assert r.status_code == 401


def test_garbage_token_is_401(client):
    r = client.post(
        "/urls",
        json={"original_url": "https://example.com"},
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert r.status_code == 401
