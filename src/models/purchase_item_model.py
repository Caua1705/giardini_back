import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.base import Base
from src.models.inventory_enums import status_item_compra


class PurchaseItem(Base):
    """Item da nota.

    A metade de cima é o que a nota diz, literal, sem interpretação. A de baixo é o
    que a gente entendeu — e um CHECK no banco garante que item sem mapeamento não
    tem `quantidade_base`, ou seja, não vira movimento.
    """

    __tablename__ = "compras_itens"
    __table_args__ = {"schema": "giardini_estoque"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    compra_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("giardini_estoque.compras.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)

    descricao_fiscal: Mapped[str] = mapped_column(Text, nullable=False)
    codigo_fiscal: Mapped[str | None] = mapped_column(Text, nullable=True)
    ncm: Mapped[str | None] = mapped_column(Text, nullable=True)
    cfop: Mapped[str | None] = mapped_column(Text, nullable=True)
    gtin: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantidade_fiscal: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unidade_fiscal: Mapped[str] = mapped_column(Text, nullable=False)
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    insumo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("giardini_estoque.insumos.id"), nullable=True
    )
    mapeamento_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("giardini_estoque.mapeamento_fornecedor.id"),
        nullable=True,
    )
    fator_aplicado: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    quantidade_base: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    custo_unitario_base: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)

    status: Mapped[str] = mapped_column(
        status_item_compra, nullable=False, default="precisa_mapeamento"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    compra: Mapped["Purchase"] = relationship("Purchase", back_populates="itens")
