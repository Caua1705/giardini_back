from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Numeric, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.db.base import Base


class FinanceTransaction(Base):
    """Read-only normalized revenue transaction loaded by the n8n ETL."""

    __tablename__ = "receitas_transacoes"
    __table_args__ = {"schema": "giardini_financeiro"}

    eye_transaction_id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    data: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    data_hora: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    subtotal: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    discount: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    total: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    transaction_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    origem: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
