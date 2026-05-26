import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.repositories.expense_repository import ExpenseRepository
from src.repositories.finance_repository import FinanceRepository
from src.schemas.admin_expense import (
    AdminExpenseCategoryResponse,
    AdminExpenseItemResponse,
    AdminExpenseListResponse,
    AdminExpenseSummaryResponse,
)
from src.schemas.admin_finance import (
    AdminRevenuePaymentInsightResponse,
    AdminRevenueProductResponse,
    AdminRevenueResponse,
    AdminRevenueSalesByDayResponse,
    AdminRevenueSalesByHourResponse,
    AdminRevenueSummaryResponse,
)


logger = logging.getLogger(__name__)


class AdminFinanceService:
    """Coordinates admin finance analytics and expense reporting."""

    def __init__(self, db: Session):
        self.finance_repo = FinanceRepository(db)
        self.expense_repo = ExpenseRepository(db)

    def get_revenue(self, start_date: date, end_date: date) -> AdminRevenueResponse:
        """Build revenue analytics from normalized database tables only."""
        if start_date > end_date:
            raise ValueError("start_date must be before or equal to end_date")

        logger.info(
            "Loading finance revenue analytics from database: start_date=%s end_date=%s",
            start_date,
            end_date,
        )

        summary = self.finance_repo.get_revenue_summary(
            start_date=start_date,
            end_date=end_date,
        )
        top_products = self.finance_repo.get_top_products(
            start_date=start_date,
            end_date=end_date,
        )
        sales_by_hour = self.finance_repo.get_sales_by_hour(
            start_date=start_date,
            end_date=end_date,
        )
        sales_by_day = self.finance_repo.get_sales_by_day(
            start_date=start_date,
            end_date=end_date,
        )
        payment_insights = self.finance_repo.get_payment_insights(
            start_date=start_date,
            end_date=end_date,
        )

        return AdminRevenueResponse(
            summary=AdminRevenueSummaryResponse(
                revenue_total=self._to_float(summary["revenue_total"]),
                transactions=summary["transactions"],
                ticket_average=self._to_float(summary["ticket_average"]),
            ),
            top_products=[
                AdminRevenueProductResponse(
                    product_name=product["product_name"],
                    quantity=self._to_float(product["quantity"]),
                    revenue=self._to_float(product["revenue"]),
                )
                for product in top_products
            ],
            sales_by_hour=[
                AdminRevenueSalesByHourResponse(
                    hour=row["hour"],
                    revenue=self._to_float(row["revenue"]),
                    transactions=row["transactions"],
                )
                for row in sales_by_hour
            ],
            sales_by_day=[
                AdminRevenueSalesByDayResponse(
                    date=row["date"],
                    revenue=self._to_float(row["revenue"]),
                    transactions=row["transactions"],
                )
                for row in sales_by_day
            ],
            payment_insights=[
                AdminRevenuePaymentInsightResponse(
                    type=row["type"],
                    revenue=self._to_float(row["revenue"]),
                    transactions=row["transactions"],
                )
                for row in payment_insights
            ],
            start_date=start_date,
            end_date=end_date,
            source="database",
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

    def _to_float(self, value: Decimal | int | float | None) -> float:
        return float(value or 0)
