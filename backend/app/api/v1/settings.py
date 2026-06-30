"""Print pricing settings routes."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_roles
from app.core.roles import UserRole
from app.database import get_db
from app.models.user import User
from app.schemas import PrintPriceResponse, PrintPriceUpdate
from app.services.audit import log_action
from app.services.print_pricing import get_or_create_print_settings, update_print_price

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/print-price", response_model=PrintPriceResponse)
async def get_print_price_setting(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await get_or_create_print_settings(db)
    return PrintPriceResponse(
        price_per_photo=settings.price_per_photo,
        currency="EGP",
        updated_at=settings.updated_at,
    )


@router.patch("/print-price", response_model=PrintPriceResponse)
async def update_print_price_setting(
    payload: PrintPriceUpdate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    settings = await update_print_price(db, payload.price_per_photo, current_user.id)
    await log_action(
        db,
        user_id=current_user.id,
        action="update_print_price",
        entity_type="print_settings",
        entity_id=settings.id,
        ip_address=request.client.host if request.client else None,
    )
    return PrintPriceResponse(
        price_per_photo=settings.price_per_photo,
        currency="EGP",
        updated_at=settings.updated_at,
    )
