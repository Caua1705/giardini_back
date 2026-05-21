from datetime import date
from pydantic import BaseModel


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
