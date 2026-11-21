# URL Shortener API

A URL shortener built with **FastAPI**, **PostgreSQL** and **Redis**. It has JWT auth, per-user links, optional expiry, click counts, and a cache-aside Redis layer that keeps serving redirects even when Redis is down.

## Architecture

```
            ┌──────────────┐  1. GET url:{code}  ┌─────────┐
 client ──► │  FastAPI API │ ──────────────────► │  Redis  │
  GET /abc  │              │ ◄── hit: 307 ────── │ (cache) │
            │              │                     └─────────┘
            │              │  2. miss → SELECT   ┌──────────┐
            │              │ ──────────────────► │ Postgres │  (source of truth)
            │              │  3. SET url:{code} EX ttl → Redis
            └──────────────┘
```

**Read path (cache-aside).** A redirect checks Redis first. On a miss it reads Postgres, checks expiry, and writes the result to Redis with a TTL.

**Write path.** Postgres is written first. The cache is written only after the commit succeeds, and it's invalidated after the row is deleted, so Redis never holds a link that Postgres doesn't.

## Design decisions

| Decision | Why |
|---|---|
| Every cache key has a TTL: `min(link lifetime, 24h)` | Bounds memory, and a cached link can never outlive its expiry |
| Redis errors are caught and treated as a miss (200 ms timeout) | If Redis goes down, redirects get slower but keep working instead of returning 500s |
| Invalidate the cache **after** the DB delete commits | If it were deleted first, a concurrent redirect could re-cache the row before the delete lands |
| Short codes: 7 chars, base62, from `secrets` | 62⁷ ≈ 3.5 × 10¹² codes; they aren't predictable, so they can't be enumerated |
| Collisions are handled by the `UNIQUE` constraint and a retry | "SELECT then INSERT" races under concurrent requests; the database constraint is the real guard |
| `307` redirect, not `301` | Browsers cache 301s permanently, which would break expiry, deletion and click counting |
| Click counts use Redis `INCR` | Counting a click doesn't hit Postgres. Trade-off: counts are lost if Redis loses its data. A next step would be flushing counts to Postgres in batches. |
| JWT algorithm pinned on decode | Blocks `alg=none` / algorithm-confusion tokens |
| Passwords hashed with bcrypt, capped at 72 bytes | bcrypt silently ignores bytes past 72, so the limit is enforced explicitly |
| Owner-only access to `GET` and `DELETE /urls/{id}` | 403 for other users' links |

## Performance

The redirect path was measured with k6 (`loadtest/redirect.js`): 20 virtual users, 30 s, mean of 3 runs, local Docker setup.

| Config | Throughput | p95 latency |
|---|---|---|
| Postgres only (`CACHE_ENABLED=false`) | 610 req/s | 110.8 ms |
| With Redis cache | 919 req/s | 39.1 ms |

**About 65% lower p95 latency and about 50% higher throughput.** These numbers were measured on v1.0. To reproduce them:

```bash
docker compose up -d --build
k6 run loadtest/redirect.js                                # cache on
CACHE_ENABLED=false docker compose up -d api && k6 run loadtest/redirect.js   # cache off
```

## Run it

```bash
docker compose up --build        # API on http://localhost:8000, docs at /docs
```

Locally, without Docker:

```bash
cp .env.example .env             # point it at your Postgres + Redis
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

## API

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | – | Create an account |
| POST | `/auth/login` | – | Get a JWT |
| POST | `/urls` | ✓ | Shorten a URL (`expires_in` in seconds is optional) |
| GET | `/urls` | ✓ | List your links with click counts |
| GET | `/urls/{id}` | ✓ owner | One link with its click count |
| DELETE | `/urls/{id}` | ✓ owner | Delete the link and invalidate the cache |
| GET | `/{short_code}` | – | 307 redirect |
| GET | `/health` | – | Database and Redis status |

```bash
curl -X POST localhost:8000/auth/register -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"password123"}'
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"password123"}' | jq -r .access_token)
curl -X POST localhost:8000/urls -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"original_url":"https://fastapi.tiangolo.com","expires_in":3600}'
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

There are 18 tests covering auth (401s, duplicate emails, bad tokens), redirects, cache population and TTLs, **fallback to Postgres when Redis is down**, expiry, cache invalidation on delete, ownership checks (403), and click counting. They use SQLite and fakeredis, so no services are needed.

## Next steps

- Alembic migrations instead of `create_all`
- Flush click counters from Redis to Postgres in batches
- Per-IP rate limiting on `POST /urls`
- Custom aliases
