import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.api.dependencies.admin_auth import validate_admin_or_internal
from src.api.dependencies.date_range import DateRange, date_range_params
from src.db.session import get_db
from src.schemas.admin_expense import AdminExpenseListResponse
from src.schemas.admin_finance import (
    AdminFinanceAnalysisOverviewResponse,
    AdminRevenueResponse,
    CategoriesAnalysisResponse,
    ProductsAnalysisResponse,
)
from src.services.admin_finance_service import AdminFinanceService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/finance", tags=["Admin Finance"])


@router.get(
    "/analysis/categories",
    response_model=CategoriesAnalysisResponse,
    summary="Get finance expense category analysis",
    dependencies=[Depends(validate_admin_or_internal)],
)
def get_admin_finance_categories_analysis(
    period: DateRange = Depends(date_range_params),
    db: Session = Depends(get_db),
):
    service = AdminFinanceService(db)
    period = period.require_both_or_none()

    try:
        return service.get_categories_analysis(
            start_date=period.start_date,
            end_date=period.end_date,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except SQLAlchemyError:
        logger.exception("Could not load finance categories analysis")
        raise HTTPException(status_code=500, detail="Could not load finance categories analysis")


@router.get(
    "/analysis/products",
    response_model=ProductsAnalysisResponse,
    summary="Get finance product and hourly sales analysis",
    dependencies=[Depends(validate_admin_or_internal)],
)
def get_admin_finance_products_analysis(
    period: DateRange = Depends(date_range_params),
    db: Session = Depends(get_db),
):
    service = AdminFinanceService(db)
    period = period.require_both_or_none()

    try:
        return service.get_products_analysis(
            start_date=period.start_date,
            end_date=period.end_date,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except SQLAlchemyError:
        logger.exception("Could not load finance products analysis")
        raise HTTPException(status_code=500, detail="Could not load finance products analysis")


@router.get(
    "/analysis/overview",
    response_model=AdminFinanceAnalysisOverviewResponse,
    summary="Get consolidated finance analysis overview",
    dependencies=[Depends(validate_admin_or_internal)],
)
def get_admin_finance_analysis_overview(
    period: DateRange = Depends(date_range_params),
    db: Session = Depends(get_db),
):
    service = AdminFinanceService(db)
    period = period.require_both_or_none()

    try:
        return service.get_analysis_overview(
            start_date=period.start_date,
            end_date=period.end_date,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except SQLAlchemyError:
        logger.exception("Could not load finance analysis overview")
        raise HTTPException(status_code=500, detail="Could not load finance analysis overview")


@router.get(
    "/revenue",
    response_model=AdminRevenueResponse,
    summary="Get database-backed revenue analytics",
    dependencies=[Depends(validate_admin_or_internal)],
)
def get_admin_revenue(
    period: DateRange = Depends(date_range_params),
    db: Session = Depends(get_db),
):
    service = AdminFinanceService(db)
    start_date, end_date = period.require_both()

    try:
        return service.get_revenue(start_date=start_date, end_date=end_date)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except SQLAlchemyError:
        logger.exception("Could not load revenue analytics")
        raise HTTPException(status_code=500, detail="Could not load revenue analytics")


@router.get(
    "/expenses",
    response_model=AdminExpenseListResponse,
    summary="List admin finance expenses",
    dependencies=[Depends(validate_admin_or_internal)],
)
def list_admin_expenses(
    period: DateRange = Depends(date_range_params),
    category: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    service = AdminFinanceService(db)

    try:
        return service.list_expenses(
            start_date=period.start_date,
            end_date=period.end_date,
            category=category,
            search=search,
            limit=limit,
            offset=offset,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except SQLAlchemyError:
        logger.exception("Could not load expenses")
        raise HTTPException(status_code=500, detail="Could not load expenses")
