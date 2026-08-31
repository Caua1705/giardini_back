import uuid
from datetime import datetime

from sqlalchemy import Integer, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.db.base import Base
from src.models.inventory_enums import status_documento, tipo_documento


class Document(Base):
    """Arquivo recebido. O hash único é a primeira barreira contra reprocessar."""

    __tablename__ = "documentos"
    __table_args__ = {"schema": "giardini_estoque"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    hash_sha256: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    tipo: Mapped[str] = mapped_column(tipo_documento, nullable=False)
    nome_arquivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime: Mapped[str | None] = mapped_column(Text, nullable=True)
    tamanho_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    chave_nfe: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(status_documento, nullable=False, default="recebido")
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)

    recebido_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    processado_em: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
