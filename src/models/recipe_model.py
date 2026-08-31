import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Integer, Numeric, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.base import Base


class Recipe(Base):
    """Ficha técnica de um produto do cardápio.

    `eye_product_id` é a ligação com a venda: o product_id do PDV Eyemobile, que
    passa a ser gravado em giardini_financeiro.receitas_transacao_itens. Não é o
    nome do produto — o nome já existe no banco em duas grafias para o mesmo item.

    Versionada: mudar a receita em setembro não pode mudar o CMV de agosto.
    """

    __tablename__ = "ficha_tecnica"
    __table_args__ = {"schema": "giardini_estoque"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    eye_product_id: Mapped[str] = mapped_column(Text, nullable=False)
    nome_produto: Mapped[str] = mapped_column(Text, nullable=False)  # snapshot legível
    rendimento: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=1)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    valid_from: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    valid_to: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    itens: Mapped[list["RecipeItem"]] = relationship(
        "RecipeItem", back_populates="ficha", cascade="all, delete-orphan"
    )
