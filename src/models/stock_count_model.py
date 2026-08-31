import uuid
from datetime import datetime

from sqlalchemy import Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.base import Base
from src.models.inventory_enums import status_contagem


class StockCount(Base):
    """Inventário periódico. Fechar a contagem gera um ajuste por item com
    diferença — é assim que ela vira saldo sem quebrar o append-only."""

    __tablename__ = "contagens"
    __table_args__ = {"schema": "giardini_estoque"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    realizada_em: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    responsavel: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(status_contagem, nullable=False, default="aberta")
    fechada_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    itens: Mapped[list["StockCountItem"]] = relationship(
        "StockCountItem", back_populates="contagem", cascade="all, delete-orphan"
    )
