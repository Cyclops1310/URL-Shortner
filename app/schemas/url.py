from datetime import datetime

from pydantic import BaseModel, HttpUrl


class URLCreate(BaseModel):
    original_url: HttpUrl
    expires_in: int | None = None


class URLResponse(BaseModel):
    id: int
    short_code: str
    original_url: HttpUrl
    expires_at: datetime | None
    click_count: int

    class Config:
        from_attributes = True


class URLUpdate(BaseModel):
    original_url: HttpUrl | None = None
    expires_in: int | None = None