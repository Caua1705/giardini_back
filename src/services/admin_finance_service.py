import json
from datetime import date
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from src.core.config import (
    EYE_PDV_ACCESS_KEY,
    EYE_PDV_REVENUE_URL,
    EYE_PDV_SECRET_KEY,
)
from src.repositories.expense_repository import ExpenseRepository
from src.schemas.admin_expense import (
    AdminExpenseCategoryResponse,
    AdminExpenseItemResponse,
    AdminExpenseListResponse,
    AdminExpenseSummaryResponse,
)
from src.schemas.admin_finance import (
    AdminRevenuePaymentTypeResponse,
    AdminRevenueResponse,
)


EYE_PDV_TRANSACTION_LIMIT = 100
EYE_PDV_TRANSACTION_TYPES = "0,15,18"


class EyePdvError(Exception):
    pass


class EyePdvConfigError(Exception):
    pass


class AdminFinanceService:
    def __init__(self, db: Session | None = None):
        self.expense_repo = ExpenseRepository(db) if db else None

    def get_revenue(self, start: str, end: str) -> AdminRevenueResponse:
        if not EYE_PDV_REVENUE_URL:
            raise EyePdvConfigError("Eye PDV configuration is missing")

        if not EYE_PDV_ACCESS_KEY or not EYE_PDV_SECRET_KEY:
            raise EyePdvConfigError("Eye PDV configuration is missing")

        transactions = self._fetch_eye_pdv_transactions(start=start, end=end)
        metrics = self._calculate_revenue_metrics(transactions)

        return AdminRevenueResponse(
            receita_total=float(metrics["receita_total"]),
            quantidade_transacoes=metrics["quantidade_transacoes"],
            quantidade_pagamentos=metrics["quantidade_pagamentos"],
            ticket_medio=float(metrics["ticket_medio"]),
            pagamentos_por_tipo=[
                AdminRevenuePaymentTypeResponse(
                    tipo=payment_type,
                    total=float(values["total"]),
                    quantidade=values["quantidade"],
                )
                for payment_type, values in metrics["pagamentos_por_tipo"].items()
            ],
            start=start,
            end=end,
            source="eye_pdv",
        )

    def list_expenses(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        category: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AdminExpenseListResponse:
        if not self.expense_repo:
            raise ValueError("Expense repository is not available")

        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be before or equal to end_date")

        category = category.strip().upper() if category and category.strip() else None
        search = search.strip() if search and search.strip() else None

        summary = self.expense_repo.get_admin_expenses_summary(
            start_date=start_date,
            end_date=end_date,
            category=category,
            search=search,
        )
        by_category = self.expense_repo.get_admin_expenses_by_category(
            start_date=start_date,
            end_date=end_date,
            category=category,
            search=search,
        )
        expenses = self.expense_repo.list_admin_expenses(
            start_date=start_date,
            end_date=end_date,
            category=category,
            search=search,
            limit=limit,
            offset=offset,
        )

        return AdminExpenseListResponse(
            summary=AdminExpenseSummaryResponse(
                total_expenses=float(summary["total_expenses"]),
                expenses_count=summary["expenses_count"],
                highest_expense=float(summary["highest_expense"]),
                top_category=summary["top_category"],
            ),
            by_category=[
                AdminExpenseCategoryResponse(
                    category=category_summary["category"],
                    total=float(category_summary["total"]),
                    count=category_summary["count"],
                )
                for category_summary in by_category
            ],
            items=[
                AdminExpenseItemResponse(
                    id=expense.id,
                    descricao=expense.descricao or "",
                    data=expense.data,
                    valor=float(expense.valor),
                    categoria=expense.categoria,
                    comprovante_url=expense.comprovante_url,
                )
                for expense in expenses
            ],
        )

    def _fetch_eye_pdv_transactions(self, start: str, end: str) -> list[dict]:
        transactions = []
        offset = 0

        while True:
            payload = self._fetch_eye_pdv_transactions_page(
                start=start,
                end=end,
                limit=EYE_PDV_TRANSACTION_LIMIT,
                offset=offset,
            )
            transactions.extend(self._extract_transactions(payload))

            if not self._has_more(payload):
                break

            offset += EYE_PDV_TRANSACTION_LIMIT

        return transactions

    def _fetch_eye_pdv_transactions_page(
        self,
        start: str,
        end: str,
        limit: int,
        offset: int,
    ):
        url = self._build_url(start=start, end=end, limit=limit, offset=offset)
        headers = {
            "Accept": "application/json",
            "X-EYEMOBILE-ACCESS-KEY": EYE_PDV_ACCESS_KEY,
            "X-EYEMOBILE-SECRET-KEY": EYE_PDV_SECRET_KEY,
        }
        request = Request(url, headers=headers, method="GET")

        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise EyePdvError(f"Eye PDV returned status {error.code}") from error
        except URLError as error:
            raise EyePdvError("Could not connect to Eye PDV") from error
        except json.JSONDecodeError as error:
            raise EyePdvError("Eye PDV returned invalid JSON") from error

    def _build_url(self, start: str, end: str, limit: int, offset: int) -> str:
        parts = urlsplit(EYE_PDV_REVENUE_URL)
        path = self._build_transactions_path(parts.path)
        query = urlencode(
            {
                "limit": limit,
                "offset": offset,
                "start": start,
                "end": end,
                "cancelled": "false",
                "serialized_types": EYE_PDV_TRANSACTION_TYPES,
            },
            safe=",",
        )
        separator = "&" if parts.query else ""

        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                path,
                f"{parts.query}{separator}{query}",
                parts.fragment,
            )
        )

    def _build_transactions_path(self, path: str) -> str:
        path = path.rstrip("/")

        if path.endswith("/transactions") or path == "transactions":
            return f"/{path.lstrip('/')}"

        return f"/{path.lstrip('/')}/transactions" if path else "/transactions"

    def _extract_transactions(self, payload) -> list[dict]:
        if isinstance(payload, list):
            return payload

        if not isinstance(payload, dict):
            raise EyePdvError("Eye PDV response does not contain transactions")

        for key in ("data", "items", "transactions", "results"):
            transactions = payload.get(key)
            if isinstance(transactions, list):
                return transactions

        raise EyePdvError("Eye PDV response does not contain transactions")

    def _has_more(self, payload) -> bool:
        return isinstance(payload, dict) and payload.get("has_more") is True

    def _calculate_revenue_metrics(self, transactions: list[dict]) -> dict:
        receita_total = Decimal("0")
        quantidade_transacoes = 0
        quantidade_pagamentos = 0
        pagamentos_por_tipo = {}

        for transaction in transactions:
            if not self._is_valid_transaction(transaction):
                continue

            quantidade_transacoes += 1

            for payment in transaction["transaction_pays"]:
                payment_total = self._extract_payment_total(payment)

                if payment_total is None:
                    continue

                payment_type = self._extract_payment_type_name(payment)

                receita_total += payment_total
                quantidade_pagamentos += 1

                if payment_type not in pagamentos_por_tipo:
                    pagamentos_por_tipo[payment_type] = {
                        "total": Decimal("0"),
                        "quantidade": 0,
                    }

                pagamentos_por_tipo[payment_type]["total"] += payment_total
                pagamentos_por_tipo[payment_type]["quantidade"] += 1

        ticket_medio = Decimal("0")

        if quantidade_transacoes > 0:
            ticket_medio = receita_total / Decimal(quantidade_transacoes)

        return {
            "receita_total": receita_total,
            "quantidade_transacoes": quantidade_transacoes,
            "quantidade_pagamentos": quantidade_pagamentos,
            "ticket_medio": ticket_medio,
            "pagamentos_por_tipo": pagamentos_por_tipo,
        }

    def _is_valid_transaction(self, transaction: dict) -> bool:
        return (
            isinstance(transaction, dict)
            and transaction.get("completed") is True
            and transaction.get("cancelled") is False
            and isinstance(transaction.get("transaction_pays"), list)
        )

    def _extract_payment_total(self, payment: dict) -> Decimal | None:
        if not isinstance(payment, dict):
            return None

        pay_type = payment.get("pay_type")

        if not isinstance(pay_type, dict) or pay_type.get("totalize") is not True:
            return None

        total = payment.get("total")

        if isinstance(total, bool) or not isinstance(total, (int, float)):
            return None

        decimal_total = Decimal(str(total))

        if not decimal_total.is_finite():
            return None

        return decimal_total

    def _extract_payment_type_name(self, payment: dict) -> str:
        pay_type = payment.get("pay_type")

        if not isinstance(pay_type, dict):
            return "Não informado"

        for field in ("name", "description", "label"):
            value = pay_type.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()

        return "Não informado"
