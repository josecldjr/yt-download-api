from sqlalchemy import Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApiConfiguration(Base):
    __tablename__ = "api_configuration"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    require_api_authentication: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
