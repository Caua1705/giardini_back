import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class RecipeItem(Base):
    """Insumo e quantidade de uma ficha técnica.

    `perda_percentual` existe porque a planilha traz rendimento líquido: a cebola
    que vira 80% de cebola picada.
    """

    __tablename__ = "ficha_tecnica_itens"
    __table_args__ = {"schema": "giardini_estoque"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ficha_tecnica_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("giardini_estoque.ficha_tecnica.id", ondelete="CASCADE"),
        nullable=False,
    )
    insumo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("giardini_estoque.insumos.id"), nullable=False
    )
    quantidade_base: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    perda_percentual: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    ficha: Mapped["Recipe"] = relationship("Recipe", back_populates="itens")
