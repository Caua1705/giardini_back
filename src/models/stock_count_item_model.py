import uuid
from decimal import Decimal

from sqlalchemy import Computed, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class StockCountItem(Base):
    """Item contado. `diferenca` é coluna gerada no banco, não calculada aqui."""

    __tablename__ = "contagens_itens"
    __table_args__ = {"schema": "giardini_estoque"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contagem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("giardini_estoque.contagens.id", ondelete="CASCADE"),
        nullable=False,
    )
    insumo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("giardini_estoque.insumos.id"), nullable=False
    )
    quantidade_contada: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantidade_sistema: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    diferenca: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4),
        Computed("quantidade_contada - quantidade_sistema", persisted=True),
        nullable=True,
    )
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    contagem: Mapped["StockCount"] = relationship("StockCount", back_populates="itens")
