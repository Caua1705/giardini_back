"""Schemas do domínio de estoque.

Leitura devolve o envelope de `tool_envelope` (é tool da Júlia). Escrita usa
corpo próprio e o `{"detail": ...}` do FastAPI, como o PATCH de reservas — não
é tool e nunca entra na lista de ferramentas.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# ESCRITA — registrar compra
# ============================================================================

class FornecedorEntrada(BaseModel):
    cnpj: str | None = None
    razao_social: str
    nome_fantasia: str | None = None

    @field_validator("cnpj")
    @classmethod
    def so_digitos(cls, v: str | None) -> str | None:
        if v is None:
            return None
        digitos = "".join(c for c in v if c.isdigit())
        if len(digitos) != 14:
            raise ValueError("CNPJ deve ter 14 dígitos.")
        return digitos


class DocumentoEntrada(BaseModel):
    hash_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tipo: Literal["nfce", "comprovante", "outro"] = "nfce"
    nome_arquivo: str | None = None
    mime: str | None = None
    tamanho_bytes: int | None = None
    storage_path: str | None = None


class ItemNotaEntrada(BaseModel):
    """Um item como a nota o descreve. Nada aqui é interpretado."""

    ordem: int = Field(ge=1)
    descricao_fiscal: str
    codigo_fiscal: str | None = None
    ncm: str | None = None
    cfop: str | None = None
    gtin: str | None = None
    quantidade_fiscal: Decimal = Field(gt=0)
    unidade_fiscal: str
    valor_unitario: Decimal = Field(ge=0)
    valor_total: Decimal = Field(ge=0)


class CompraEntrada(BaseModel):
    # Chave de idempotência da operação: reenviar a mesma nota devolve a compra
    # que já existe, não cria outra.
    chave_nfe: str | None = Field(default=None, pattern=r"^[0-9]{44}$")
    fornecedor: FornecedorEntrada
    numero_nota: str | None = None
    serie: str | None = None
    emitida_em: datetime | None = None
    valor_total: Decimal = Field(ge=0)
    valor_desconto: Decimal = Field(default=Decimal("0"), ge=0)
    documento: DocumentoEntrada | None = None
    itens: list[ItemNotaEntrada] = Field(min_length=1)

    @field_validator("itens")
    @classmethod
    def ordens_unicas(cls, v: list[ItemNotaEntrada]) -> list[ItemNotaEntrada]:
        ordens = [i.ordem for i in v]
        if len(set(ordens)) != len(ordens):
            raise ValueError("Cada item precisa de uma `ordem` única dentro da nota.")
        return v


class ItemCompraResposta(BaseModel):
    id: str
    ordem: int
    descricao_fiscal: str
    codigo_fiscal: str | None
    quantidade_fiscal: Decimal
    unidade_fiscal: str
    valor_total: Decimal
    status: str
    insumo: str | None = None
    quantidade_base: Decimal | None = None


class CompraResposta(BaseModel):
    id: str
    chave_nfe: str | None
    fornecedor: str
    numero_nota: str | None
    valor_total: Decimal
    status: str
    # true quando a nota já tinha sido registrada: a requisição foi idempotente
    # e nada novo foi criado.
    ja_existia: bool
    itens_total: int
    itens_mapeados: int
    itens_pendentes: int
    despesa_id: int | None
    despesa_vinculada: bool
    itens: list[ItemCompraResposta]


# ============================================================================
# ESCRITA — confirmar mapeamento de um item
# ============================================================================

class MapearItemEntrada(BaseModel):
    insumo_codigo: str
    unidade_fiscal: str
    # Quantidade na unidade base por 1 unidade fiscal. 1 caixa de 30 ovos = 30.
    fator_conversao: Decimal = Field(gt=0)
    confirmado_por: str
    observacao: str | None = None


class MapearItemResposta(BaseModel):
    mapeamento_id: str
    compra_id: str
    item_id: str
    insumo: str
    fator_conversao: Decimal
    quantidade_base: Decimal
    custo_unitario_base: Decimal
    movimento_id: str | None
    compra_status: str
    itens_pendentes: int
    substituiu_mapeamento_id: str | None


# ============================================================================
# ESCRITA — contagem
# ============================================================================

class ItemContagemEntrada(BaseModel):
    insumo_codigo: str
    quantidade_contada: Decimal = Field(ge=0)
    observacao: str | None = None


class ContagemEntrada(BaseModel):
    # Chave da operação: repetir a mesma requisição devolve a contagem existente.
    chave_idempotencia: str = Field(min_length=8, max_length=200)
    realizada_em: datetime
    responsavel: str
    observacao: str | None = None
    fechar: bool = True
    itens: list[ItemContagemEntrada] = Field(min_length=1)


class ItemContagemResposta(BaseModel):
    insumo: str
    quantidade_contada: Decimal
    quantidade_sistema: Decimal | None
    diferenca: Decimal | None
    movimento_id: str | None


class ContagemResposta(BaseModel):
    id: str
    status: str
    ja_existia: bool
    itens: list[ItemContagemResposta]
    ajustes_gerados: int


# ============================================================================
# ESCRITA — perda
# ============================================================================

class PerdaEntrada(BaseModel):
    chave_idempotencia: str = Field(min_length=8, max_length=200)
    insumo_codigo: str
    # Sempre positiva no corpo; o movimento é gravado com sinal negativo.
    quantidade: Decimal = Field(gt=0)
    motivo: str
    ocorreu_em: datetime | None = None


class PerdaResposta(BaseModel):
    movimento_id: str
    insumo: str
    quantidade: Decimal
    unidade_base: str
    ja_existia: bool


# ============================================================================
# LEITURA — filtros nomeados (as respostas vão no envelope, não aqui)
# ============================================================================

STATUS_COMPRA_VALIDOS = ("rascunho", "revisao", "aprovada", "lancada", "cancelada")

# Janela fixa do consumo médio usado em cobertura_dias. Não é parâmetro: menos
# parâmetro é menos chance de o agente errar, e a janela vai escrita em `avisos`.
JANELA_CONSUMO_DIAS = 30
