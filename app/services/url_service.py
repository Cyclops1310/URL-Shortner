from datetime import datetime, timedelta, timezone
import random
import string

from sqlalchemy.orm import Session

from app.models.url import URL
from app.redis_client import redis_client


def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits

    return "".join(
        random.choice(characters)
        for _ in range(length)
    )


def create_short_url(
    db: Session,
    original_url: str,
    user_id: int,
    expires_in: int | None = None
):
    # Generate a unique short code
    while True:
        short_code = generate_short_code()

        existing = db.query(URL).filter(
            URL.short_code == short_code
        ).first()

        if not existing:
            break

    # Calculate expiration time
    expires_at = None

    if expires_in:
        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=expires_in)
        )

    # Save URL in PostgreSQL
    url = URL(
        short_code=short_code,
        original_url=original_url,
        user_id=user_id,
        expires_at=expires_at
    )

    db.add(url)
    db.commit()
    db.refresh(url)

    # Save URL in Redis
    cache_key = f"url:{short_code}"

    if expires_in:
        redis_client.set(
            cache_key,
            original_url,
            ex=expires_in
        )
    else:
        redis_client.set(
            cache_key,
            original_url
        )

    return url


def get_url_by_short_code(
    db: Session,
    short_code: str
):
    cache_key = f"url:{short_code}"

    # 1. Check Redis first
    cached_url = redis_client.get(cache_key)

    if cached_url:
        return cached_url

    # 2. Redis miss → PostgreSQL
    url = db.query(URL).filter(
        URL.short_code == short_code
    ).first()

    if not url:
        return None

    # 3. Check expiration
    if url.expires_at:
        now = datetime.now(timezone.utc)

        if url.expires_at <= now:
            return None

        remaining_seconds = int(
            (url.expires_at - now).total_seconds()
        )

        redis_client.set(
            cache_key,
            url.original_url,
            ex=remaining_seconds
        )

    else:
        redis_client.set(
            cache_key,
            url.original_url
        )

    return url.original_url


def delete_url(
    db: Session,
    url: URL
):
    cache_key = f"url:{url.short_code}"

    # Delete from PostgreSQL
    db.delete(url)
    db.commit()

    # Remove from Redis
    redis_client.delete(cache_key)