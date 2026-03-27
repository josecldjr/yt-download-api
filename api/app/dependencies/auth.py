from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_management_access(authorization: str | None = Header(default=None)) -> None:
    expected = settings.management_secret.strip()
    provided = ""

    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            provided = token.strip()

    if not expected or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid management credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
