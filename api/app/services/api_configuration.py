from sqlalchemy.orm import Session

from app.models.api_configuration import ApiConfiguration


DEFAULT_QUALITY = "1080p"
QUALITY_OPTIONS = ["720p", "1080p", "1440p", "4k", "best"]


def get_or_create_api_configuration(db: Session) -> ApiConfiguration:
    configuration = db.get(ApiConfiguration, 1)
    if configuration is not None:
        return configuration

    configuration = ApiConfiguration(id=1, require_api_authentication=True)
    db.add(configuration)
    db.commit()
    db.refresh(configuration)
    return configuration
