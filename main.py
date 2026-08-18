from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
import redis
import random
import string


app = FastAPI()


# Connect to Redis
r = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)


# Request body
class URLRequest(BaseModel):
    url: HttpUrl


# Generate random short code
def generate_short_code(length=5):
    characters = string.ascii_letters + string.digits

    return "".join(
        random.choice(characters)
        for _ in range(length)
    )


# Create short URL
@app.post("/shorten")
def shorten_url(request: URLRequest):

    while True:
        short_code = generate_short_code()

        # Check whether this code already exists
        if not r.exists(short_code):
            break

    # Store short code -> original URL
    r.set(
        short_code,
        str(request.url),
        ex=3600
    )

    return {
        "short_code": short_code,
        "short_url": f"http://localhost:8000/{short_code}"
    }


# Redirect to original URL
@app.get("/{short_code}")
def redirect_to_url(short_code: str):

    original_url = r.get(short_code)

    if original_url is None:
        raise HTTPException(
            status_code=404,
            detail="Short URL not found or expired"
        )

    return RedirectResponse(url=original_url)


# Check remaining lifetime
@app.get("/ttl/{short_code}")
def check_ttl(short_code: str):

    ttl = r.ttl(short_code)

    if ttl == -2:
        raise HTTPException(
            status_code=404,
            detail="Short URL not found"
        )

    return {
        "short_code": short_code,
        "remaining_seconds": ttl
    }