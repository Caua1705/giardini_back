from datetime import date
from decimal import Decimal

from sqlalchemy import cast, func
from sqlalchemy.orm import Session
from sqlalchemy.types import Date, Integer, String

from src.models import FinanceTransaction, FinanceTransactionItem


REALIZED_REVENUE_TRANSACTION_TYPE = "0"


class FinanceRepository:
    """Read-only analytics repository for normalized finance ETL tables."""

    def __init__(self, db: Session):
        self.db = db

    def get_revenue_summary(self, start_date: date, end_date: date) -> dict:
        """Return total revenue, transaction count, and average ticket."""
        revenue_total, transactions, ticket_average = (
            self._realized_transactions_base_query(start_date=start_date, end_date=end_date)
            .with_entities(
                func.coalesce(func.sum(FinanceTransaction.total), 0),
                func.count(FinanceTransaction.eye_transaction_id),
                func.coalesce(func.avg(FinanceTransaction.total), 0),
            )
            .one()
        )

        return {
            "revenue_total": revenue_total or Decimal("0"),
            "transactions": transactions,
            "ticket_average": ticket_average or Decimal("0"),
        }

    def get_top_products(
        self,
        start_date: date,
        end_date: date,
        limit: int = 10,
    ) -> list[dict]:
        """Return product ranking by sold amount and quantity."""
        rows = (
            self._items_base_query(start_date=start_date, end_date=end_date)
            .join(
                FinanceTransaction,
                FinanceTransaction.eye_transaction_id == FinanceTransactionItem.transaction_id,
            )
            .filter(FinanceTransaction.transaction_type == REALIZED_REVENUE_TRANSACTION_TYPE)
            .with_entities(
                FinanceTransactionItem.product_name.label("product_name"),
                func.coalesce(func.sum(FinanceTransactionItem.quantity), 0).label("quantity"),
                func.coalesce(func.sum(FinanceTransactionItem.total), 0).label("revenue"),
            )
            .group_by(FinanceTransactionItem.product_name)
            .order_by(func.sum(FinanceTransactionItem.total).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "product_name": row.product_name,
                "quantity": row.quantity or Decimal("0"),
                "revenue": row.revenue or Decimal("0"),
            }
            for row in rows
        ]

    def get_sales_by_hour(
        self,
        start_date: date,
        end_date: date,
        timezone: str | None = None,
    ) -> list[dict]:
        """Return revenue and transaction count grouped by transaction hour."""
        transaction_time = (
            func.timezone(timezone, FinanceTransaction.data_hora)
            if timezone
            else FinanceTransaction.data_hora
        )
        hour = cast(func.extract("hour", transaction_time), Integer)

        rows = (
            self._realized_transactions_base_query(start_date=start_date, end_date=end_date)
            .filter(FinanceTransaction.data_hora.isnot(None))
            .with_entities(
                hour.label("hour"),
                func.coalesce(func.sum(FinanceTransaction.total), 0).label("revenue"),
                func.count(FinanceTransaction.eye_transaction_id).label("transactions"),
            )
            .group_by(hour)
            .order_by(hour.asc())
            .all()
        )

        return [
            {
                "hour": int(row.hour),
                "revenue": row.revenue or Decimal("0"),
                "transactions": row.transactions,
            }
            for row in rows
        ]

    def get_sales_by_day(self, start_date: date, end_date: date) -> list[dict]:
        """Return revenue and transaction count grouped by day."""
        rows = (
            self._realized_transactions_base_query(start_date=start_date, end_date=end_date)
            .with_entities(
                FinanceTransaction.data.label("date"),
                func.coalesce(func.sum(FinanceTransaction.total), 0).label("revenue"),
                func.count(FinanceTransaction.eye_transaction_id).label("transactions"),
            )
            .group_by(FinanceTransaction.data)
            .order_by(FinanceTransaction.data.asc())
            .all()
        )

        return [
            {
                "date": row.date,
                "revenue": row.revenue or Decimal("0"),
                "transactions": row.transactions,
            }
            for row in rows
        ]

    def get_payment_insights(self, start_date: date, end_date: date) -> list[dict]:
        """Return available transaction-type distribution from normalized data."""
        transaction_type = func.coalesce(
            cast(FinanceTransaction.transaction_type, String),
            "unknown",
        )

        rows = (
            self._realized_transactions_base_query(start_date=start_date, end_date=end_date)
            .with_entities(
                transaction_type.label("type"),
                func.coalesce(func.sum(FinanceTransaction.total), 0).label("revenue"),
                func.count(FinanceTransaction.eye_transaction_id).label("transactions"),
            )
            .group_by(transaction_type)
            .order_by(func.sum(FinanceTransaction.total).desc())
            .all()
        )

        return [
            {
                "type": row.type,
                "revenue": row.revenue or Decimal("0"),
                "transactions": row.transactions,
            }
            for row in rows
        ]

    def list_transactions_with_items(self, start_date: date, end_date: date) -> list[dict]:
        """Return detailed transactions with their items without N+1 queries."""
        transactions = (
            self._realized_transactions_base_query(start_date=start_date, end_date=end_date)
            .order_by(FinanceTransaction.data_hora.asc(), FinanceTransaction.eye_transaction_id.asc())
            .all()
        )

        if not transactions:
            return []

        transaction_ids = [
            transaction.eye_transaction_id
            for transaction in transactions
        ]

        items = (
            self.db.query(FinanceTransactionItem)
            .filter(FinanceTransactionItem.transaction_id.in_(transaction_ids))
            .order_by(
                FinanceTransactionItem.transaction_time.asc(),
                FinanceTransactionItem.product_name.asc(),
            )
            .all()
        )

        items_by_transaction_id: dict[str, list[FinanceTransactionItem]] = {}
        for item in items:
            items_by_transaction_id.setdefault(item.transaction_id, []).append(item)

        return [
            {
                "transaction": transaction,
                "items": items_by_transaction_id.get(transaction.eye_transaction_id, []),
            }
            for transaction in transactions
        ]

    def _transactions_base_query(self, start_date: date, end_date: date):
        return (
            self.db.query(FinanceTransaction)
            .filter(FinanceTransaction.data >= start_date)
            .filter(FinanceTransaction.data <= end_date)
        )

    def _realized_transactions_base_query(self, start_date: date, end_date: date):
        return (
            self._transactions_base_query(start_date=start_date, end_date=end_date)
            .filter(FinanceTransaction.transaction_type == REALIZED_REVENUE_TRANSACTION_TYPE)
        )

    def _items_base_query(self, start_date: date, end_date: date):
        transaction_date = cast(FinanceTransactionItem.transaction_time, Date)

        return (
            self.db.query(FinanceTransactionItem)
            .filter(FinanceTransactionItem.transaction_time.isnot(None))
            .filter(transaction_date >= start_date)
            .filter(transaction_date <= end_date)
        )
