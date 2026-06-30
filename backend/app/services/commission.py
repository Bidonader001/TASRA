"""Employee commission calculation based on monthly photo targets."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_target import EmployeeMonthlyTarget
from app.models.sale import Sale

BASE_COMMISSION_EGP = 6.0
BONUS_COMMISSION_EGP = 12.0  # doubled after target


@dataclass
class CommissionBreakdown:
    employee_id: int
    year: int
    month: int
    target_photos: int
    photos_printed: int
    photos_at_base_rate: int
    photos_at_bonus_rate: int
    base_commission: float
    bonus_commission: float
    total_commission: float
    target_met: bool
    progress_percent: float


def month_range(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


async def get_photos_printed_in_month(
    db: AsyncSession, employee_id: int, year: int, month: int
) -> int:
    start, end = month_range(year, month)
    result = await db.execute(
        select(func.coalesce(func.sum(Sale.photo_count), 0)).where(
            Sale.employee_id == employee_id,
            Sale.created_at >= start,
            Sale.created_at < end,
        )
    )
    return int(result.scalar() or 0)


async def get_employee_target(
    db: AsyncSession, employee_id: int, year: int, month: int
) -> EmployeeMonthlyTarget | None:
    result = await db.execute(
        select(EmployeeMonthlyTarget).where(
            EmployeeMonthlyTarget.employee_id == employee_id,
            EmployeeMonthlyTarget.year == year,
            EmployeeMonthlyTarget.month == month,
        )
    )
    return result.scalar_one_or_none()


def calculate_commission(photos_printed: int, target_photos: int) -> CommissionBreakdown:
    target = max(target_photos, 0)
    photos = max(photos_printed, 0)
    at_base = min(photos, target) if target > 0 else photos
    at_bonus = max(0, photos - target) if target > 0 else 0
    base_commission = round(at_base * BASE_COMMISSION_EGP, 2)
    bonus_commission = round(at_bonus * BONUS_COMMISSION_EGP, 2)
    progress = round((photos / target * 100), 1) if target > 0 else 0.0
    return CommissionBreakdown(
        employee_id=0,
        year=0,
        month=0,
        target_photos=target,
        photos_printed=photos,
        photos_at_base_rate=at_base,
        photos_at_bonus_rate=at_bonus,
        base_commission=base_commission,
        bonus_commission=bonus_commission,
        total_commission=round(base_commission + bonus_commission, 2),
        target_met=photos >= target if target > 0 else False,
        progress_percent=min(progress, 100.0) if target > 0 else 0.0,
    )


async def get_commission_breakdown(
    db: AsyncSession, employee_id: int, year: int, month: int
) -> CommissionBreakdown:
    target_row = await get_employee_target(db, employee_id, year, month)
    target_photos = target_row.target_photos if target_row else 0
    photos_printed = await get_photos_printed_in_month(db, employee_id, year, month)
    breakdown = calculate_commission(photos_printed, target_photos)
    breakdown.employee_id = employee_id
    breakdown.year = year
    breakdown.month = month
    if target_photos > 0 and photos_printed > target_photos:
        breakdown.progress_percent = round((photos_printed / target_photos) * 100, 1)
    return breakdown
