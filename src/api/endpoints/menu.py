from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.menu_service import MenuService
from src.schemas.menu import MenuItemResponse

router = APIRouter()

@router.get(
    "/menu",
    response_model=list[MenuItemResponse],
    status_code=200,
    summary="Get menu items",
    description="Returns all active menu items from the public menu view.",
)
def get_menu(
    db: Session = Depends(get_db),
):
    service = MenuService(db)
    try:
        return service.get_menu()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
