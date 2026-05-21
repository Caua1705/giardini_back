from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Expense(Base):
    __tablename__ = "despesas"
    __table_args__ = {"schema": "giardini_financeiro"}

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    descricao: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    data: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    valor: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    comprovante_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    categoria: Mapped[str] = mapped_column(
        ENUM(
            "FOLHA",
            "FIXO",
            "OPERACIONAL",
            "INSUMOS",
            "OBRA",
            name="categoria_despesa",
            schema="giardini_financeiro",
            create_type=False,
        ),
        nullable=False,
    )
