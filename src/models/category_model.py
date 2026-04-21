import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.base import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id"),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    sort_order: Mapped[int | None] = mapped_column(
        Integer,
        default=0,
        nullable=True,
    )

    is_active: Mapped[bool | None] = mapped_column(
        Boolean,
        default=True,
        nullable=True,
    )

    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=True,
    )

    # Relacionamentos
    parent: Mapped["Category | None"] = relationship(
    "Category",
    remote_side=[id],
    back_populates="subcategories",
    )

    subcategories: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
    )

    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="category",
    )
