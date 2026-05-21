from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models import Expense


class ExpenseRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_admin_expenses(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        category: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Expense]:
        query = self._admin_base_query(
            start_date=start_date,
            end_date=end_date,
            category=category,
            search=search,
        )

        return (
            query
            .order_by(
                Expense.data.desc(),
                Expense.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_admin_expenses_summary(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> dict:
        query = self._admin_base_query(
            start_date=start_date,
            end_date=end_date,
            category=category,
            search=search,
        )

        total_expenses, expenses_count, highest_expense = query.with_entities(
            func.coalesce(func.sum(Expense.valor), 0),
            func.count(Expense.id),
            func.coalesce(func.max(Expense.valor), 0),
        ).one()

        top_category_row = (
            query
            .with_entities(
                Expense.categoria,
                func.coalesce(func.sum(Expense.valor), 0).label("total"),
            )
            .group_by(Expense.categoria)
            .order_by(func.sum(Expense.valor).desc())
            .first()
        )

        return {
            "total_expenses": total_expenses or Decimal("0"),
            "expenses_count": expenses_count,
            "highest_expense": highest_expense or Decimal("0"),
            "top_category": top_category_row.categoria if top_category_row else None,
        }

    def get_admin_expenses_by_category(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        query = self._admin_base_query(
            start_date=start_date,
            end_date=end_date,
            category=category,
            search=search,
        )

        rows = (
            query
            .with_entities(
                Expense.categoria.label("category"),
                func.coalesce(func.sum(Expense.valor), 0).label("total"),
                func.count(Expense.id).label("expense_count"),
            )
            .group_by(Expense.categoria)
            .order_by(func.sum(Expense.valor).desc())
            .all()
        )

        return [
            {
                "category": row.category,
                "total": row.total or Decimal("0"),
                "count": row.expense_count,
            }
            for row in rows
        ]

    def _admin_base_query(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        category: str | None = None,
        search: str | None = None,
    ):
        query = self.db.query(Expense)

        if start_date:
            query = query.filter(Expense.data >= start_date)

        if end_date:
            query = query.filter(Expense.data <= end_date)

        if category:
            query = query.filter(Expense.categoria == category)

        if search:
            query = query.filter(Expense.descricao.ilike(f"%{search}%"))

        return query
