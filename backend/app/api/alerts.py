"""Per-device threshold alert rules and their current status.

Minimal by design (the brief): a rule is a sensor + comparator + threshold, and
"status" evaluates each rule against that sensor's most recent reading. Visible
in the dashboard only — no email/SMS.
"""

import operator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.alert import AlertRule
from app.models.device import Device
from app.models.telemetry import Telemetry
from app.models.user import User
from app.schemas.alert import AlertRuleCreate, AlertRuleRead, AlertStatus

router = APIRouter(prefix="/devices", tags=["alerts"])

_COMPARATORS = {
    "lt": operator.lt,
    "lte": operator.le,
    "gt": operator.gt,
    "gte": operator.ge,
}


async def _owned_device_or_404(device_id: int, user: User, session: AsyncSession) -> Device:
    device = await session.scalar(
        select(Device).where(Device.id == device_id, Device.user_id == user.id)
    )
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.post(
    "/{device_id}/alerts",
    response_model=AlertRuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a threshold alert rule for a device",
)
async def create_alert_rule(
    device_id: int,
    payload: AlertRuleCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlertRule:
    await _owned_device_or_404(device_id, current_user, session)
    rule = AlertRule(
        device_id=device_id,
        sensor_name=payload.sensor_name,
        comparator=payload.comparator,
        threshold=payload.threshold,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


@router.get(
    "/{device_id}/alerts",
    response_model=list[AlertRuleRead],
    summary="List a device's alert rules",
)
async def list_alert_rules(
    device_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AlertRule]:
    await _owned_device_or_404(device_id, current_user, session)
    result = await session.scalars(
        select(AlertRule).where(AlertRule.device_id == device_id).order_by(AlertRule.id)
    )
    return list(result)


@router.delete(
    "/{device_id}/alerts/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an alert rule",
)
async def delete_alert_rule(
    device_id: int,
    rule_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await _owned_device_or_404(device_id, current_user, session)
    rule = await session.scalar(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.device_id == device_id)
    )
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found")
    await session.delete(rule)
    await session.commit()


@router.get(
    "/{device_id}/alerts/status",
    response_model=list[AlertStatus],
    summary="Evaluate a device's alert rules against the latest readings",
)
async def alert_status(
    device_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AlertStatus]:
    await _owned_device_or_404(device_id, current_user, session)

    rules = list(
        await session.scalars(
            select(AlertRule).where(AlertRule.device_id == device_id).order_by(AlertRule.id)
        )
    )

    # Latest value per sensor for this device (DISTINCT ON (sensor_name)).
    latest_rows = (
        await session.execute(
            select(Telemetry.sensor_name, Telemetry.value, Telemetry.time)
            .where(Telemetry.device_id == device_id)
            .distinct(Telemetry.sensor_name)
            .order_by(Telemetry.sensor_name, Telemetry.time.desc())
        )
    ).all()
    latest = {row[0]: (row[1], row[2]) for row in latest_rows}

    statuses: list[AlertStatus] = []
    for rule in rules:
        value, when = latest.get(rule.sensor_name, (None, None))
        triggered = value is not None and _COMPARATORS[rule.comparator](value, rule.threshold)
        statuses.append(
            AlertStatus(
                rule_id=rule.id,
                sensor_name=rule.sensor_name,
                comparator=rule.comparator,
                threshold=rule.threshold,
                latest_value=value,
                latest_time=when,
                triggered=triggered,
            )
        )
    return statuses
