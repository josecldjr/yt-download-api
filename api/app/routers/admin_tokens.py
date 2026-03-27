from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.dependencies.auth import require_management_access
from app.models.access_token import AccessToken
from app.schemas.access_token import AccessTokenCreate, AccessTokenResponse, AccessTokenUpdate
from app.services.token_cipher import TokenCipher

router = APIRouter(
    prefix="/admin/access-tokens",
    tags=["admin"],
    dependencies=[Depends(require_management_access)],
)

token_cipher = TokenCipher()


def _to_response(model: AccessToken) -> AccessTokenResponse:
    return AccessTokenResponse(
        id=model.id,
        name=model.name,
        description=model.description,
        content=token_cipher.decrypt(model.content),
    )


@router.get(
    "",
    response_model=list[AccessTokenResponse],
    summary="List access tokens",
    description="Returns all stored access tokens with decrypted content for management purposes.",
)
async def list_access_tokens(db: Session = Depends(get_db_session)) -> list[AccessTokenResponse]:
    records = db.scalars(select(AccessToken).order_by(AccessToken.name.asc())).all()
    return [_to_response(record) for record in records]


@router.post(
    "",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create access token",
    description="Creates a new stored access token and encrypts its content before saving.",
)
async def create_access_token(
    payload: AccessTokenCreate,
    db: Session = Depends(get_db_session),
) -> AccessTokenResponse:
    record = AccessToken(
        name=payload.name.strip(),
        description=payload.description.strip(),
        content=token_cipher.encrypt(payload.content.strip()),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_response(record)


@router.put(
    "/{token_id}",
    response_model=AccessTokenResponse,
    summary="Update access token",
    description="Updates a stored access token and replaces its encrypted content.",
)
async def update_access_token(
    token_id: str,
    payload: AccessTokenUpdate,
    db: Session = Depends(get_db_session),
) -> AccessTokenResponse:
    record = db.get(AccessToken, token_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access token not found.")

    record.name = payload.name.strip()
    record.description = payload.description.strip()
    record.content = token_cipher.encrypt(payload.content.strip())
    db.commit()
    db.refresh(record)
    return _to_response(record)


@router.delete(
    "/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete access token",
    description="Deletes an access token from the local SQLite database.",
)
async def delete_access_token(
    token_id: str,
    db: Session = Depends(get_db_session),
) -> None:
    record = db.get(AccessToken, token_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access token not found.")

    db.delete(record)
    db.commit()
