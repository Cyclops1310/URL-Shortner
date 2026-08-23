from fastapi import FastAPI

from app.database import engine, Base
from app.models.user import User
from app.models.url import URL
from app.routes import auth, urls


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Redis URL Shortener",
    description="URL shortener using FastAPI, PostgreSQL and Redis",
    version="1.0.0"
)


app.include_router(auth.router)
app.include_router(urls.router)


@app.get("/")
def root():
    return {
        "message": "Redis URL Shortener API is running"
    }