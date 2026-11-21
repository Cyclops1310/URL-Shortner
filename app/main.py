from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.cache import cache
from app.database import Base, SessionLocal, engine
from app.models import url, user  # noqa: F401  (register models on Base)
from app.routes import auth, urls


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Fine for a portfolio project; a production service would use Alembic migrations.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="URL Shortener",
    description="URL shortener with FastAPI, PostgreSQL and Redis (cache-aside).",
    version="1.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
def health():
    db_ok = True
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"database": db_ok, "redis": cache.ping()}


app.include_router(auth.router)
app.include_router(urls.router)  # last: contains the catch-all "/{short_code}"
