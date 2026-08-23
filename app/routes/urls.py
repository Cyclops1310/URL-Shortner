from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.url import URL
from app.schemas.url import URLCreate
from app.services.url_service import (
    create_short_url,
    get_url_by_short_code,
    delete_url
)


router = APIRouter(tags=["URLs"])


@router.post("/urls")
def create_url(
    request: URLCreate,
    db: Session = Depends(get_db)
):
    user_id = 1

    url = create_short_url(
        db=db,
        original_url=str(request.original_url),
        user_id=user_id,
        expires_in=request.expires_in
    )

    return {
        "id": url.id,
        "short_code": url.short_code,
        "short_url": f"http://127.0.0.1:8000/{url.short_code}",
        "original_url": url.original_url,
        "expires_at": url.expires_at,
        "click_count": url.click_count
    }


@router.get("/{short_code}")
def redirect_to_original(
    short_code: str,
    db: Session = Depends(get_db)
):
    original_url = get_url_by_short_code(
        db=db,
        short_code=short_code
    )

    if not original_url:
        raise HTTPException(
            status_code=404,
            detail="Short URL not found or expired"
        )

    return RedirectResponse(
        url=original_url,
        status_code=307
    )


@router.delete("/urls/{url_id}")
def remove_url(
    url_id: int,
    db: Session = Depends(get_db)
):
    url = db.query(URL).filter(
        URL.id == url_id
    ).first()

    if not url:
        raise HTTPException(
            status_code=404,
            detail="URL not found"
        )

    delete_url(
        db=db,
        url=url
    )

    return {
        "message": "URL deleted successfully"
    }