from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.dependencies.auth import require_management_access
from app.schemas.api_configuration import (
    AdminApiConfigurationResponse,
    AdminApiConfigurationUpdate,
    PublicApiConfigurationResponse,
)
from app.services.api_configuration import (
    DEFAULT_QUALITY,
    DEFAULT_MAX_TRANSCRIPTION_UPLOAD_SIZE_MB,
    QUALITY_OPTIONS,
    get_or_create_api_configuration,
)

router = APIRouter(tags=["settings"])
admin_router = APIRouter(
    prefix="/admin/settings",
    tags=["admin"],
    dependencies=[Depends(require_management_access)],
)


def _to_public_response(require_api_authentication: bool) -> PublicApiConfigurationResponse:
    return PublicApiConfigurationResponse(
        require_api_authentication=require_api_authentication,
        default_quality=DEFAULT_QUALITY,
        quality_options=QUALITY_OPTIONS,
    )


def _to_admin_response(configuration: object) -> AdminApiConfigurationResponse:
    return AdminApiConfigurationResponse(
        require_api_authentication=configuration.require_api_authentication,
        default_quality=DEFAULT_QUALITY,
        quality_options=QUALITY_OPTIONS,
        max_transcription_upload_size_mb=(
            configuration.max_transcription_upload_size_mb
            or DEFAULT_MAX_TRANSCRIPTION_UPLOAD_SIZE_MB
        ),
    )


@router.get(
    "/settings/public",
    response_model=PublicApiConfigurationResponse,
    summary="Get public API configuration",
    description="Returns frontend-facing settings such as available download qualities and whether API authentication is required.",
)
async def get_public_api_configuration(
    db: Session = Depends(get_db_session),
) -> PublicApiConfigurationResponse:
    configuration = get_or_create_api_configuration(db)
    return _to_public_response(configuration.require_api_authentication)


@admin_router.get(
    "/downloads",
    response_model=AdminApiConfigurationResponse,
    summary="Get download configuration",
    description="Returns the current download authentication policy and available quality options for management clients.",
)
async def get_admin_api_configuration(
    db: Session = Depends(get_db_session),
) -> AdminApiConfigurationResponse:
    configuration = get_or_create_api_configuration(db)
    return _to_admin_response(configuration)


@admin_router.put(
    "/downloads",
    response_model=AdminApiConfigurationResponse,
    summary="Update download configuration",
    description="Updates whether the public download endpoint requires an API access token.",
)
async def update_admin_api_configuration(
    payload: AdminApiConfigurationUpdate,
    db: Session = Depends(get_db_session),
) -> AdminApiConfigurationResponse:
    configuration = get_or_create_api_configuration(db)
    configuration.require_api_authentication = payload.require_api_authentication
    if payload.max_transcription_upload_size_mb is not None:
        configuration.max_transcription_upload_size_mb = payload.max_transcription_upload_size_mb
    db.commit()
    db.refresh(configuration)
    return _to_admin_response(configuration)
