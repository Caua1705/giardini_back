from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies.admin_auth import get_current_admin_user
from src.schemas.admin_finance import AdminRevenueResponse
from src.services.admin_finance_service import (
    AdminFinanceService,
    EyePdvConfigError,
    EyePdvError,
)


router = APIRouter(prefix="/admin/finance", tags=["Admin Finance"])


@router.get(
    "/revenue",
    response_model=AdminRevenueResponse,
    summary="Get Eye PDV revenue summary",
    dependencies=[Depends(get_current_admin_user)],
)
def get_admin_revenue(
    start: str = Query(...),
    end: str = Query(...),
):
    service = AdminFinanceService()

    try:
        return service.get_revenue(start=start, end=end)
    except EyePdvConfigError as error:
        raise HTTPException(status_code=500, detail=str(error))
    except EyePdvError as error:
        raise HTTPException(status_code=502, detail=str(error))
