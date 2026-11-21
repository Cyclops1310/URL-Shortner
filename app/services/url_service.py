"""URL business logic.

Read path is cache-aside:
    redirect -> Redis GET -> hit: return
                           -> miss: Postgres -> populate Redis with a TTL
Writes go to Postgres first (source of truth); the cache entry is written
after commit and deleted on delete, so Redis never holds a URL that
Postgres does not.
"""
import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cache import cache
from app.config import settings
from app.models.url import URL

ALPHABET = string.ascii_letters + string.digits  # base62
MAX_CODE_ATTEMPTS = 5


def _url_key(code: str) -> str:
    return f"url:{code}"


def _clicks_key(code: str) -> str:
    return f"clicks:{code}"


def _as_utc(dt: datetime) -> datetime:
    # Postgres returns aware datetimes; SQLite returns naive ones (stored as UTC).
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _cache_ttl(expires_at: datetime | None) -> int:
    """Cache no longer than the link lives, and never longer than the cap."""
    if expires_at is None:
        return settings.CACHE_TTL_SECONDS
    remaining = int((_as_utc(expires_at) - datetime.now(timezone.utc)).total_seconds())
    return min(remaining, settings.CACHE_TTL_SECONDS)


def generate_short_code(length: int = settings.SHORT_CODE_LENGTH) -> str:
    # secrets, not random: codes shouldn't be predictable/enumerable.
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def create_short_url(
    db: Session, original_url: str, user_id: int, expires_in: int | None = None
) -> URL:
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        if expires_in
        else None
    )

    # Rely on the UNIQUE constraint instead of "SELECT then INSERT":
    # the check-then-insert pattern races under concurrent requests.
    for _ in range(MAX_CODE_ATTEMPTS):
        url = URL(
            short_code=generate_short_code(),
            original_url=original_url,
            user_id=user_id,
            expires_at=expires_at,
        )
        db.add(url)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(url)
        cache.set(_url_key(url.short_code), url.original_url, _cache_ttl(expires_at))
        return url

    raise RuntimeError("could not generate a unique short code")


def resolve(db: Session, short_code: str) -> str | None:
    """Return the target URL for a redirect, or None if missing/expired."""
    cached = cache.get(_url_key(short_code))
    if cached:
        cache.incr(_clicks_key(short_code))
        return cached

    url = db.query(URL).filter(URL.short_code == short_code).first()
    if url is None:
        return None
    if url.expires_at and _as_utc(url.expires_at) <= datetime.now(timezone.utc):
        return None

    cache.set(_url_key(short_code), url.original_url, _cache_ttl(url.expires_at))
    cache.incr(_clicks_key(short_code))
    return url.original_url


def click_count(short_code: str) -> int:
    return cache.get_int(_clicks_key(short_code))


def delete_url(db: Session, url: URL) -> None:
    code = url.short_code
    db.delete(url)
    db.commit()
    # Invalidate after commit: if we deleted the cache first, a concurrent
    # redirect could re-populate it from the not-yet-deleted row.
    cache.delete(_url_key(code))
    cache.delete(_clicks_key(code))
