"""Sales management routes."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import require_roles
from app.core.roles import UserRole
from app.database import get_db
from app.models.customer import Customer
from app.models.sale import Sale
from app.models.user import User
from app.schemas import MessageResponse, PaginatedResponse, SaleCreate, SaleResponse, SaleUpdate
from app.services.audit import log_action
from app.services.print_pricing import calculate_sale_amount, get_print_price
from app.services.reports import export_csv, export_excel, format_report_filename
from app.utils.helpers import get_manager_employee_ids, paginate, pagination_meta

router = APIRouter(prefix="/sales", tags=["Sales"])


def sale_to_response(sale: Sale) -> SaleResponse:
    customer_name = sale.customer.name if sale.customer else None
    employee_name = f"{sale.employee.first_name} {sale.employee.last_name}" if sale.employee else None
    return SaleResponse(
        id=sale.id,
        customer_id=sale.customer_id,
        employee_id=sale.employee_id,
        photo_count=sale.photo_count,
        price_per_photo=sale.price_per_photo,
        amount=sale.amount,
        notes=sale.notes,
        created_at=sale.created_at,
        customer_name=customer_name,
        employee_name=employee_name,
    )


async def _scoped_sales_query(current_user: User, db: AsyncSession):
    stmt = select(Sale).options(selectinload(Sale.customer), selectinload(Sale.employee))
    if current_user.role == UserRole.EMPLOYEE.value:
        stmt = stmt.where(Sale.employee_id == current_user.id)
    elif current_user.role == UserRole.MANAGER.value:
        employee_ids = await get_manager_employee_ids(db, current_user.id)
        stmt = stmt.where(Sale.employee_id.in_(employee_ids or [-1]))
    return stmt


@router.get("", response_model=PaginatedResponse[SaleResponse])
async def list_sales(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.EMPLOYEE)),
    db: AsyncSession = Depends(get_db),
):
    stmt = await _scoped_sales_query(current_user, db)
    sort_col = getattr(Sale, sort_by, Sale.created_at)
    stmt = stmt.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
    items, total = await paginate(db, stmt, page, page_size)
    return PaginatedResponse(
        items=[sale_to_response(s) for s in items],
        **pagination_meta(total, page, page_size),
    )


@router.post("", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
async def create_sale(
    payload: SaleCreate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.EMPLOYEE, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Customer).where(Customer.id == payload.customer_id)
    if current_user.role == UserRole.EMPLOYEE.value:
        stmt = stmt.where(Customer.created_by_employee_id == current_user.id)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Customer not found")

    price_per_photo = await get_print_price(db)
    amount = calculate_sale_amount(payload.photo_count, price_per_photo)
    sale = Sale(
        customer_id=payload.customer_id,
        employee_id=current_user.id,
        photo_count=payload.photo_count,
        price_per_photo=price_per_photo,
        amount=amount,
        notes=payload.notes,
    )
    db.add(sale)
    await db.flush()
    await db.refresh(sale, ["customer", "employee"])
    await log_action(
        db,
        user_id=current_user.id,
        action="create_sale",
        entity_type="sale",
        entity_id=sale.id,
        ip_address=request.client.host if request.client else None,
    )
    return sale_to_response(sale)


@router.get("/{sale_id}", response_model=SaleResponse)
async def get_sale(
    sale_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.EMPLOYEE)),
    db: AsyncSession = Depends(get_db),
):
    stmt = (await _scoped_sales_query(current_user, db)).where(Sale.id == sale_id)
    result = await db.execute(stmt)
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale_to_response(sale)


@router.patch("/{sale_id}", response_model=SaleResponse)
async def update_sale(
    sale_id: int,
    payload: SaleUpdate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.EMPLOYEE, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Sale).options(selectinload(Sale.customer), selectinload(Sale.employee)).where(Sale.id == sale_id)
    if current_user.role == UserRole.EMPLOYEE.value:
        stmt = stmt.where(Sale.employee_id == current_user.id)
    result = await db.execute(stmt)
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    data = payload.model_dump(exclude_unset=True)
    if "photo_count" in data:
        sale.photo_count = data.pop("photo_count")
        sale.amount = calculate_sale_amount(sale.photo_count, sale.price_per_photo)
    for key, value in data.items():
        setattr(sale, key, value)
    await log_action(
        db,
        user_id=current_user.id,
        action="update_sale",
        entity_type="sale",
        entity_id=sale.id,
        ip_address=request.client.host if request.client else None,
    )
    return sale_to_response(sale)


@router.get("/export/{format}")
async def export_sales(
    format: str,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Sale).options(selectinload(Sale.customer), selectinload(Sale.employee)).order_by(Sale.created_at.desc())
    result = await db.execute(stmt)
    sales = result.scalars().all()
    headers = ["id", "customer", "employee", "photos_printed", "price_per_photo", "amount_egp", "notes", "created_at"]
    rows = [
        {
            "id": s.id,
            "customer": s.customer.name if s.customer else "",
            "employee": f"{s.employee.first_name} {s.employee.last_name}" if s.employee else "",
            "photos_printed": s.photo_count,
            "price_per_photo": s.price_per_photo,
            "amount_egp": s.amount,
            "notes": s.notes or "",
            "created_at": s.created_at.isoformat(),
        }
        for s in sales
    ]
    if format == "csv":
        content = export_csv(rows, headers)
        media = "text/csv"
    elif format == "excel":
        content = export_excel(rows, headers, "Sales")
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        raise HTTPException(status_code=400, detail="Use csv or excel format")
    filename = format_report_filename("sales", format if format != "excel" else "xlsx")
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
