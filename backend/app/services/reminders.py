import re

from app.core.errors import AppError
from app.models.commercial import Customer, MessageTemplate
from app.models.store import Store
from app.services.commercial import render_template


def normalize_product(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def validate_reminder_sources(
    *, customer: Customer | None, template: MessageTemplate | None, store: Store
) -> tuple[Customer, MessageTemplate]:
    if not customer or customer.store_id != store.id:
        raise AppError(404, "customer_not_found", "Cliente não encontrado nesta loja.")
    if not customer.is_active:
        raise AppError(409, "inactive_customer", "O cliente está inativo.")
    if not customer.has_consent:
        raise AppError(409, "consent_required", "O cliente não possui consentimento ativo.")
    if not template or template.store_id != store.id:
        raise AppError(404, "template_not_found", "Modelo não encontrado nesta loja.")
    if not template.is_active:
        raise AppError(409, "inactive_template", "O modelo está inativo.")
    return customer, template


def render_reminder_message(
    *, customer: Customer, template: MessageTemplate, store: Store, product: str
) -> str:
    return render_template(
        template.content,
        name=customer.name,
        product=product,
        store=store.name,
    )
