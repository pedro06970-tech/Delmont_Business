from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.customers import router as customers_router
from app.api.routes.message_templates import router as message_templates_router
from app.api.routes.reminders import router as reminders_router
from app.api.routes.stores import router as stores_router
from app.api.routes.users import router as users_router
from app.api.routes.whatsmiau import router as whatsmiau_router
from app.api.routes.whatsmiau_webhooks import router as whatsmiau_webhooks_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(customers_router)
api_router.include_router(message_templates_router)
api_router.include_router(reminders_router)
api_router.include_router(users_router)
api_router.include_router(stores_router)
api_router.include_router(whatsmiau_router)
api_router.include_router(whatsmiau_webhooks_router)
