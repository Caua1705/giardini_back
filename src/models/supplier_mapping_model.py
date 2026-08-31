import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.db.base import Base
from src.models.inventory_enums import origem_mapeamento, status_mapeamento


class SupplierMapping(Base):
    """Fornecedor + código fiscal -> insumo + fator de conversão.

    Versionado: corrigir é fechar a linha vigente com `valid_to` e inserir outra.
    Um gatilho no banco recusa UPDATE nas colunas de identidade — sobrescrever o
    fator reescreveria o custo de compras antigas.
    """

    __tablename__ = "mapeamento_fornecedor"
    __table_args__ = {"schema": "giardini_estoque"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    fornecedor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("giardini_estoque.fornecedores.id"), nullable=False
    )
    codigo_fiscal: Mapped[str] = mapped_column(Text, nullable=False)
    descricao_fiscal: Mapped[str | None] = mapped_column(Text, nullable=True)
    gtin: Mapped[str | None] = mapped_column(Text, nullable=True)

    insumo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("giardini_estoque.insumos.id"), nullable=False
    )
    unidade_fiscal: Mapped[str] = mapped_column(Text, nullable=False)
    # Quantidade na unidade base por 1 unidade fiscal.
    fator_conversao: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    status: Mapped[str] = mapped_column(status_mapeamento, nullable=False, default="sugerido")
    origem: Mapped[str] = mapped_column(origem_mapeamento, nullable=False, default="humano")

    valid_from: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    confirmado_por: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmado_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
