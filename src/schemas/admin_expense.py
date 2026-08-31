from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class AdminExpenseItemResponse(BaseModel):
    id: int
    descricao: str
    data: date
    valor: float
    categoria: str
    comprovante_url: str | None


class AdminExpenseSummaryResponse(BaseModel):
    total_expenses: float
    expenses_count: int
    highest_expense: float
    top_category: str | None


class AdminExpenseCategoryResponse(BaseModel):
    category: str
    total: float
    count: int


class AdminExpenseListResponse(BaseModel):
    summary: AdminExpenseSummaryResponse
    by_category: list[AdminExpenseCategoryResponse]
    items: list[AdminExpenseItemResponse]


# ============================================================================
# ESCRITA — não é tool. Ver docs/CONVENCAO_TOOLS.md.
# ============================================================================

class DespesaEntrada(BaseModel):
    """O que o `insercao_despesas` já monta no nó `Normalizar Dados2`."""

    valor: Decimal = Field(ge=0)
    data: date | None = None
    categoria: str | None = None
    descricao: str | None = None
    comprovante_path: str | None = None
    # Extraidos do comprovante pelo insercao_despesas. Os dois sao opcionais:
    # comprovante ilegivel nesses campos continua sendo lancado.
    identificador_transacao: str | None = None
    cnpj_recebedor: str | None = None


class CompraCandidata(BaseModel):
    compra_id: str
    despesa_id: int
    fornecedor: str
    numero_nota: str | None
    valor: Decimal
    emitida_em: date


class DespesaResposta(BaseModel):
    # criada  — nenhuma nota esperava este comprovante; despesa nova.
    # anexada — o comprovante completou a despesa que a nota já tinha criado.
    #           Nada foi lançado de novo: é o conserto do duplo lançamento.
    # ambiguo — duas ou mais notas casam com o valor. A despesa é criada avulsa
    #           (dinheiro nunca fica sem registro) e as candidatas voltam para
    #           uma pessoa decidir.
    # repetida — este comprovante ja tinha sido lancado (mesmo identificador de
    #           transacao). Nada foi criado; devolve a despesa que ja existe.
    acao: Literal["criada", "anexada", "ambiguo", "repetida"]
    despesa_id: int
    valor: Decimal
    data: date
    categoria: str
    compra_id: str | None = None
    fornecedor: str | None = None
    numero_nota: str | None = None
    candidatas: list[CompraCandidata] = []
