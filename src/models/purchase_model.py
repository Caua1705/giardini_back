import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.base import Base
from src.models.inventory_enums import status_compra


class Purchase(Base):
    """Compra. `chave_nfe` única é a chave de idempotência: reenviar a mesma nota
    não cria uma segunda compra."""

    __tablename__ = "compras"
    __table_args__ = {"schema": "giardini_estoque"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    documento_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("giardini_estoque.documentos.id"), nullable=True
    )
    fornecedor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("giardini_estoque.fornecedores.id"), nullable=False
    )

    chave_nfe: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_nota: Mapped[str | None] = mapped_column(Text, nullable=True)
    serie: Mapped[str | None] = mapped_column(Text, nullable=True)
    emitida_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    valor_desconto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    status: Mapped[str] = mapped_column(status_compra, nullable=False, default="rascunho")
    lancada_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Vínculo com a despesa avulsa da mesma compra, para nota e comprovante não
    # virarem dois lançamentos. despesas.id é integer, não uuid.
    despesa_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("giardini_financeiro.despesas.id"), nullable=True
    )

    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    itens: Mapped[list["PurchaseItem"]] = relationship(
        "PurchaseItem", back_populates="compra", cascade="all, delete-orphan"
    )
