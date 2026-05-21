from pydantic import BaseModel


class AdminRevenuePaymentTypeResponse(BaseModel):
    tipo: str
    total: float
    quantidade: int


class AdminRevenueResponse(BaseModel):
    receita_total: float
    quantidade_transacoes: int
    quantidade_pagamentos: int
    ticket_medio: float
    pagamentos_por_tipo: list[AdminRevenuePaymentTypeResponse]
    start: str
    end: str
    source: str
