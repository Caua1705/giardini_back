import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Numeric, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.db.base import Base


class FinanceTransactionItem(Base):
    """Read-only normalized transaction item loaded by the n8n ETL."""

    __tablename__ = "receitas_transacao_itens"
    __table_args__ = {"schema": "giardini_financeiro"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    transaction_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    product_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    price: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    total: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    transaction_time: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
