import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.db.base import Base
from src.models.inventory_enums import tipo_movimento, unidade_base


class StockMovement(Base):
    """Movimento de estoque. Append-only: um gatilho no banco recusa UPDATE e
    DELETE. Erro se corrige com um `ajuste_contagem` de sinal contrário.

    `quantidade_base` é assinada — entrada positiva, saída negativa — e o saldo é
    a soma. `fator_usado` e `unidade_base` são cópia do que valia no momento, não
    referência: corrigir o mapeamento não pode reescrever a história do estoque.
    """

    __tablename__ = "estoque_movimentos"
    __table_args__ = {"schema": "giardini_estoque"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    insumo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("giardini_estoque.insumos.id"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(tipo_movimento, nullable=False)
    quantidade_base: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    unidade_base: Mapped[str] = mapped_column(unidade_base, nullable=False)
    fator_usado: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    custo_unitario: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    valor_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    compra_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("giardini_estoque.compras_itens.id"), nullable=True
    )
    contagem_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("giardini_estoque.contagens_itens.id"), nullable=True
    )
    ficha_tecnica_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("giardini_estoque.ficha_tecnica.id"), nullable=True
    )
    consumo_dia: Mapped[date | None] = mapped_column(Date, nullable=True)
    eye_product_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    ocorreu_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Chave determinística por operação. É ela que faz repetir a requisição não
    # duplicar: compra:<item>, consumo:<dia>:<produto>:<insumo>, contagem:<item>.
    chave_idempotencia: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
