import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.db.base import Base
from src.models.inventory_enums import unidade_base


class Supply(Base):
    """Insumo: o catálogo canônico do estoque."""

    __tablename__ = "insumos"
    __table_args__ = {"schema": "giardini_estoque"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Slug interno estável. É por ele que a planilha de ficha técnica se liga, para
    # que corrigir o `nome` não quebre a importação.
    codigo: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    categoria: Mapped[str | None] = mapped_column(Text, nullable=True)
    unidade_base: Mapped[str] = mapped_column(unidade_base, nullable=False)

    estoque_minimo: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    perecivel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validade_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
