from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.url import URL
from app.models.user import User
from app.schemas.url import URLCreate, URLResponse
from app.security import get_current_user
from app.services import url_service

router = APIRouter(tags=["URLs"])


def _to_response(url: URL) -> URLResponse:
    return URLResponse(
        id=url.id,
        short_code=url.short_code,
        short_url=f"{settings.BASE_URL.rstrip('/')}/{url.short_code}",
        original_url=url.original_url,
        expires_at=url.expires_at,
        click_count=url_service.click_count(url.short_code),
    )


def _get_owned_url(db: Session, url_id: int, user: User) -> URL:
    url = db.get(URL, url_id)
    if url is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "URL not found")
    if url.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your URL")
    return url


@router.post("/urls", response_model=URLResponse, status_code=status.HTTP_201_CREATED)
def create_url(
    request: URLCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    url = url_service.create_short_url(
        db=db,
        original_url=str(request.original_url),
        user_id=user.id,
        expires_in=request.expires_in,
    )
    return _to_response(url)


@router.get("/urls", response_model=list[URLResponse])
def list_my_urls(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    urls = db.query(URL).filter(URL.user_id == user.id).order_by(URL.id).all()
    return [_to_response(u) for u in urls]


@router.get("/urls/{url_id}", response_model=URLResponse)
def get_url(
    url_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _to_response(_get_owned_url(db, url_id, user))


@router.delete("/urls/{url_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_url(
    url_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    url_service.delete_url(db, _get_owned_url(db, url_id, user))


# Keep this route last: "/{short_code}" would otherwise shadow the paths above.
@router.get("/{short_code}", include_in_schema=True)
def redirect_to_original(short_code: str, db: Session = Depends(get_db)):
    target = url_service.resolve(db, short_code)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Short URL not found or expired")
    # 307 (not 301) so browsers don't cache the redirect: expiry and
    # deletion take effect immediately and every click reaches the server.
    return RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
