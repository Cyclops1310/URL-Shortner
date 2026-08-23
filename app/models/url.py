from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)

    short_code = Column(
        String(10),
        unique=True,
        nullable=False,
        index=True
    )

    original_url = Column(String, nullable=False)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    expires_at = Column(DateTime(timezone=True), nullable=True)

    click_count = Column(Integer, default=0)

    user = relationship("User", backref="urls")