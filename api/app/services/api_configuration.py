from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from app.models.api_configuration import ApiConfiguration


DEFAULT_QUALITY = "1080p"
QUALITY_OPTIONS = ["144p", "360p", "480p", "720p", "1080p", "1440p", "4k", "best"]
DEFAULT_MAX_TRANSCRIPTION_UPLOAD_SIZE_MB = 200


def ensure_api_configuration_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "api_configuration" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("api_configuration")}
    if "max_transcription_upload_size_mb" in columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE api_configuration "
                "ADD COLUMN max_transcription_upload_size_mb INTEGER NOT NULL DEFAULT 200"
            )
        )


def get_or_create_api_configuration(db: Session) -> ApiConfiguration:
    configuration = db.get(ApiConfiguration, 1)
    if configuration is not None:
        return configuration

    configuration = ApiConfiguration(
        id=1,
        require_api_authentication=True,
        max_transcription_upload_size_mb=DEFAULT_MAX_TRANSCRIPTION_UPLOAD_SIZE_MB,
    )
    db.add(configuration)
    db.commit()
    db.refresh(configuration)
    return configuration
