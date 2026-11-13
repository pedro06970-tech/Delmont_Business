import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.commercial import Customer, Reminder, SalesOpportunity
from app.models.user import User
from app.schemas.sales_opportunity import (
    CollaboratorPerformance,
    CommercialDashboardResponse,
    DashboardEvolutionPoint,
    DashboardMetrics,
    DashboardPeriod,
)

DISPLAY_TIMEZONE_NAME = "America/Fortaleza"
DISPLAY_TIMEZONE = ZoneInfo(DISPLAY_TIMEZONE_NAME)
CONVERSION_DEFINITION = (
    "Oportunidades ganhas encerradas no período ÷ oportunidades ganhas e perdidas "
    "encerradas no período × 100."
)


def normalize_period(
    date_from: date | None, date_to: date | None
) -> tuple[date, date, datetime, datetime]:
    today = datetime.now(DISPLAY_TIMEZONE).date()
    end_date = date_to or today
    start_date = date_from or (end_date - timedelta(days=29))
    if start_date > end_date:
        raise AppError(422, "invalid_period", "A data inicial não pode ser posterior à data final.")
    start_utc = datetime.combine(start_date, time.min, DISPLAY_TIMEZONE).astimezone(UTC)
    end_utc = datetime.combine(end_date + timedelta(days=1), time.min, DISPLAY_TIMEZONE).astimezone(UTC)
    return start_date, end_date, start_utc, end_utc


def build_commercial_dashboard(
    db: Session,
    *,
    store_id: uuid.UUID,
    date_from: date | None,
    date_to: date | None,
    created_by_user_id: uuid.UUID | None,
) -> CommercialDashboardResponse:
    start_date, end_date, start_utc, end_utc = normalize_period(date_from, date_to)

    customer_filters = [
        Customer.store_id == store_id,
        Customer.created_at >= start_utc,
        Customer.created_at < end_utc,
    ]
    opportunity_created_filters = [
        SalesOpportunity.store_id == store_id,
        SalesOpportunity.created_at >= start_utc,
        SalesOpportunity.created_at < end_utc,
    ]
    reminder_created_filters = [
        Reminder.store_id == store_id,
        Reminder.created_at >= start_utc,
        Reminder.created_at < end_utc,
    ]
    closed_filters = [
        SalesOpportunity.store_id == store_id,
        SalesOpportunity.closed_at >= start_utc,
        SalesOpportunity.closed_at < end_utc,
    ]
    open_at_end_filters = [
        SalesOpportunity.store_id == store_id,
        SalesOpportunity.created_at < end_utc,
        or_(SalesOpportunity.closed_at.is_(None), SalesOpportunity.closed_at >= end_utc),
    ]
    accepted_filters = [
        Reminder.store_id == store_id,
        Reminder.accepted_at >= start_utc,
        Reminder.accepted_at < end_utc,
    ]
    if created_by_user_id:
        customer_filters.append(Customer.created_by_user_id == created_by_user_id)
        opportunity_created_filters.append(SalesOpportunity.created_by_user_id == created_by_user_id)
        reminder_created_filters.append(Reminder.created_by_user_id == created_by_user_id)
        closed_filters.append(SalesOpportunity.created_by_user_id == created_by_user_id)
        open_at_end_filters.append(SalesOpportunity.created_by_user_id == created_by_user_id)
        accepted_filters.append(Reminder.created_by_user_id == created_by_user_id)

    distinct_leads = db.scalar(
        select(func.count(func.distinct(Customer.id))).where(*customer_filters)
    ) or 0
    open_opportunities = db.scalar(
        select(func.count(SalesOpportunity.id)).where(*open_at_end_filters)
    ) or 0
    scheduled_reminders = db.scalar(
        select(func.count(Reminder.id)).where(*reminder_created_filters)
    ) or 0
    accepted_messages = db.scalar(
        select(func.count(Reminder.id)).where(*accepted_filters)
    ) or 0
    won_opportunities = db.scalar(
        select(func.count(SalesOpportunity.id)).where(
            *closed_filters, SalesOpportunity.status == "won"
        )
    ) or 0
    lost_opportunities = db.scalar(
        select(func.count(SalesOpportunity.id)).where(
            *closed_filters, SalesOpportunity.status == "lost"
        )
    ) or 0
    closed_total = won_opportunities + lost_opportunities
    conversion_rate = round((won_opportunities / closed_total) * 100, 2) if closed_total else 0.0

    local_day = cast(func.timezone(DISPLAY_TIMEZONE_NAME, Reminder.created_at), Date)
    evolution_rows = db.execute(
        select(local_day.label("day"), func.count(Reminder.id).label("total"))
        .where(*reminder_created_filters)
        .group_by(local_day)
        .order_by(local_day)
    ).all()

    performance = _collaborator_performance(
        db,
        store_id=store_id,
        start_utc=start_utc,
        end_utc=end_utc,
        selected_user_id=created_by_user_id,
    )
    return CommercialDashboardResponse(
        period=DashboardPeriod(
            timezone=DISPLAY_TIMEZONE_NAME,
            date_from=start_date,
            date_to=end_date,
            start_utc=start_utc,
            end_utc_exclusive=end_utc,
        ),
        metrics=DashboardMetrics(
            distinct_leads=distinct_leads,
            open_opportunities=open_opportunities,
            scheduled_reminders=scheduled_reminders,
            accepted_messages=accepted_messages,
            won_opportunities=won_opportunities,
            lost_opportunities=lost_opportunities,
            conversion_rate=conversion_rate,
            conversion_has_basis=closed_total > 0,
            conversion_definition=CONVERSION_DEFINITION,
        ),
        reminder_evolution=[
            DashboardEvolutionPoint(date=row.day, reminders=row.total)
            for row in evolution_rows
        ],
        collaborator_performance=performance,
    )


def _collaborator_performance(
    db: Session,
    *,
    store_id: uuid.UUID,
    start_utc: datetime,
    end_utc: datetime,
    selected_user_id: uuid.UUID | None,
) -> list[CollaboratorPerformance]:
    user_filter = [SalesOpportunity.created_by_user_id == selected_user_id] if selected_user_id else []
    created_rows = db.execute(
        select(SalesOpportunity.created_by_user_id, func.count(SalesOpportunity.id))
        .where(
            SalesOpportunity.store_id == store_id,
            SalesOpportunity.created_at >= start_utc,
            SalesOpportunity.created_at < end_utc,
            *user_filter,
        )
        .group_by(SalesOpportunity.created_by_user_id)
    ).all()
    won_rows = db.execute(
        select(SalesOpportunity.created_by_user_id, func.count(SalesOpportunity.id))
        .where(
            SalesOpportunity.store_id == store_id,
            SalesOpportunity.status == "won",
            SalesOpportunity.closed_at >= start_utc,
            SalesOpportunity.closed_at < end_utc,
            *user_filter,
        )
        .group_by(SalesOpportunity.created_by_user_id)
    ).all()
    reminder_user_filter = [Reminder.created_by_user_id == selected_user_id] if selected_user_id else []
    reminder_rows = db.execute(
        select(Reminder.created_by_user_id, func.count(Reminder.id))
        .where(
            Reminder.store_id == store_id,
            Reminder.created_at >= start_utc,
            Reminder.created_at < end_utc,
            *reminder_user_filter,
        )
        .group_by(Reminder.created_by_user_id)
    ).all()
    created = dict(created_rows)
    won = dict(won_rows)
    reminders = dict(reminder_rows)
    user_ids = set(created) | set(won) | set(reminders)
    if selected_user_id:
        user_ids.add(selected_user_id)
    if not user_ids:
        return []
    names = dict(db.execute(select(User.id, User.name).where(User.id.in_(user_ids))).all())
    return sorted(
        [
            CollaboratorPerformance(
                user_id=user_id,
                user_name=names.get(user_id, "Usuário"),
                opportunities_created=created.get(user_id, 0),
                opportunities_won=won.get(user_id, 0),
                reminders_created=reminders.get(user_id, 0),
            )
            for user_id in user_ids
        ],
        key=lambda item: (-item.opportunities_won, -item.opportunities_created, item.user_name),
    )
