from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, Text
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

    comprovante_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    categoria: Mapped[str] = mapped_column(Text, nullable=False)

    # E2E do Pix ou numero do documento. Indice unico parcial: comprovante sem
    # identificador legivel continua entrando, so nao ganha a protecao contra
    # envio repetido.
    identificador_transacao: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
