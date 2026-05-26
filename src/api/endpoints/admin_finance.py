import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.api.dependencies.admin_auth import get_current_admin_user
from src.db.session import get_db
from src.schemas.admin_expense import AdminExpenseListResponse
from src.schemas.admin_finance import AdminRevenueResponse
from src.services.admin_finance_service import AdminFinanceService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/finance", tags=["Admin Finance"])


@router.get(
    "/revenue",
    response_model=AdminRevenueResponse,
    summary="Get database-backed revenue analytics",
    dependencies=[Depends(get_current_admin_user)],
)
def get_admin_revenue(
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
):
    service = AdminFinanceService(db)

    try:
        return service.get_revenue(start_date=start, end_date=end)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except SQLAlchemyError:
        logger.exception("Could not load revenue analytics")
        raise HTTPException(status_code=500, detail="Could not load revenue analytics")


@router.get(
    "/expenses",
    response_model=AdminExpenseListResponse,
    summary="List admin finance expenses",
    dependencies=[Depends(get_current_admin_user)],
)
def list_admin_expenses(
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    service = AdminFinanceService(db)

    try:
        return service.list_expenses(
            start_date=start_date,
            end_date=end_date,
            category=category,
            search=search,
            limit=limit,
            offset=offset,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Could not load expenses")
