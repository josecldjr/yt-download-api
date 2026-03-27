from hmac import compare_digest

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db_session
from app.models.access_token import AccessToken
from app.services.token_cipher import TokenCipher

management_bearer = HTTPBearer(auto_error=False)
api_bearer = HTTPBearer(auto_error=False)
token_cipher = TokenCipher()


def require_management_access(
    credentials: HTTPAuthorizationCredentials | None = Depends(management_bearer),
) -> None:
    expected = settings.management_secret.strip()
    provided = credentials.credentials.strip() if credentials else ""

    if not expected or not compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid management credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_api_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(api_bearer),
    db: Session = Depends(get_db_session),
) -> AccessToken:
    provided = credentials.credentials.strip() if credentials else ""
    if not provided:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid API access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    records = db.scalars(select(AccessToken)).all()
    for record in records:
        try:
            decrypted = token_cipher.decrypt(record.content)
        except Exception:
            continue

        if compare_digest(provided, decrypted):
            return record

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
