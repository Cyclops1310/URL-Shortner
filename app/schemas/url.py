from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class URLCreate(BaseModel):
    original_url: HttpUrl
    # Optional lifetime in seconds (max 1 year).
    expires_in: int | None = Field(default=None, gt=0, le=31_536_000)


class URLResponse(BaseModel):
    id: int
    short_code: str
    short_url: str
    original_url: str
    expires_at: datetime | None
    click_count: int
