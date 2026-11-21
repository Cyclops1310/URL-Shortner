from datetime import datetime, timedelta, timezone

import redis

from app.cache import cache
from app.database import SessionLocal
from app.models.url import URL
from tests.conftest import make_user


def create(client, auth, **body):
    body.setdefault("original_url", "https://example.com/page")
    r = client.post("/urls", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_redirect(client, auth):
    url = create(client, auth)
    assert url["short_url"].endswith(url["short_code"])

    r = client.get(f"/{url['short_code']}")
    assert r.status_code == 307
    assert r.headers["location"] == "https://example.com/page"


def test_unknown_code_is_404(client):
    assert client.get("/doesnotexist").status_code == 404


def test_cache_miss_populates_cache(client, auth):
    url = create(client, auth)
    key = f"url:{url['short_code']}"
    cache.client.delete(key)  # simulate eviction

    assert client.get(f"/{url['short_code']}").status_code == 307
    assert cache.client.get(key) == "https://example.com/page"
    assert cache.client.ttl(key) > 0  # every cache entry has a TTL


def test_redirect_falls_back_to_postgres_when_redis_is_down(client, auth):
    url = create(client, auth)

    class DownRedis:
        def __getattr__(self, _):
            def fail(*a, **k):
                raise redis.ConnectionError("down")
            return fail

    cache.client = DownRedis()
    r = client.get(f"/{url['short_code']}")
    assert r.status_code == 307


def test_expired_link_is_404(client, auth):
    url = create(client, auth, expires_in=60)
    cache.client.flushall()
    with SessionLocal() as db:
        row = db.get(URL, url["id"])
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    assert client.get(f"/{url['short_code']}").status_code == 404


def test_cache_ttl_never_outlives_link(client, auth):
    url = create(client, auth, expires_in=30)
    assert 0 < cache.client.ttl(f"url:{url['short_code']}") <= 30


def test_click_count(client, auth):
    url = create(client, auth)
    for _ in range(3):
        client.get(f"/{url['short_code']}")
    r = client.get(f"/urls/{url['id']}", headers=auth)
    assert r.json()["click_count"] == 3


def test_list_only_my_urls(client, auth):
    create(client, auth)
    bob = make_user(client, email="bob@example.com")
    create(client, bob)

    r = client.get("/urls", headers=auth)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_delete_invalidates_cache(client, auth):
    url = create(client, auth)
    r = client.delete(f"/urls/{url['id']}", headers=auth)
    assert r.status_code == 204
    assert cache.client.get(f"url:{url['short_code']}") is None
    assert client.get(f"/{url['short_code']}").status_code == 404


def test_cannot_delete_someone_elses_url(client, auth):
    url = create(client, auth)
    bob = make_user(client, email="bob@example.com")
    assert client.delete(f"/urls/{url['id']}", headers=bob).status_code == 403
    assert client.get(f"/{url['short_code']}").status_code == 307


def test_invalid_url_rejected(client, auth):
    r = client.post("/urls", json={"original_url": "not a url"}, headers=auth)
    assert r.status_code == 422


def test_health(client):
    r = client.get("/health")
    assert r.json() == {"database": True, "redis": True}
