"""Envelope padrão das rotas de tool, conforme docs/CONVENCAO_TOOLS.md §3 e §5.

Vale para os quatro domínios. O primeiro a usar é `inventory`; `finance` e
`reservations` migram quando ganharem rota de tool, sem mudar nada aqui.
"""
from typing import Any

from pydantic import BaseModel, Field


class Periodo(BaseModel):
    """O período EFETIVAMENTE consultado, não o pedido.

    É a chave que impede a Júlia de afirmar um número sobre o período errado:
    quando o pedido é ajustado, `avisos` explica a diferença.
    """

    start_date: str
    end_date: str
    rotulo: str


class Truncamento(BaseModel):
    truncado: bool = False
    retornados: int = 0
    # Sai de um COUNT de verdade, nunca estimado: truncamento silencioso é pior
    # que erro, porque o agente afirma "foram essas" quando eram as cinco primeiras.
    total: int = 0
    sugestao: str | None = None


class RespostaTool(BaseModel):
    """As quatro chaves de topo. `periodo` pode ser nulo (foto do agora), mas
    a chave está sempre presente."""

    periodo: Periodo | None
    dados: dict[str, Any]
    avisos: list[str] = Field(default_factory=list)
    truncamento: Truncamento


class Erro(BaseModel):
    codigo: str
    mensagem: str
    sugestao: str | None = None


class RespostaErro(BaseModel):
    erro: Erro


class ErroTool(Exception):
    """Erro de rota de tool. O handler em main.py converte para o envelope de §5.

    `mensagem` é escrita para ser quase repetível ao usuário final: pt-BR, uma
    frase, com os valores concretos. Nada de nome de tabela ou stack trace.
    """

    def __init__(self, status_code: int, codigo: str, mensagem: str,
                 sugestao: str | None = None) -> None:
        super().__init__(mensagem)
        self.status_code = status_code
        self.codigo = codigo
        self.mensagem = mensagem
        self.sugestao = sugestao


def rotulo_periodo(start_date, end_date) -> str:
    """Período por extenso, na forma que o brasileiro fala, pronto para o agente
    repetir na resposta."""
    from datetime import date as _date

    hoje = _date.today()

    if start_date == end_date:
        if start_date == hoje:
            return "hoje"
        if (hoje - start_date).days == 1:
            return "ontem"
        return start_date.strftime("%d/%m/%Y")

    if start_date.year == end_date.year and start_date.month == end_date.month \
            and start_date.day == 1:
        meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                 "agosto", "setembro", "outubro", "novembro", "dezembro"]
        return f"{meses[start_date.month - 1]}/{start_date.year}"

    return f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"


def monta_truncamento(retornados: int, total: int, sugestao: str) -> Truncamento:
    truncado = total > retornados
    return Truncamento(
        truncado=truncado,
        retornados=retornados,
        total=total,
        sugestao=sugestao if truncado else None,
    )
