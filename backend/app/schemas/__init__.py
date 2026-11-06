"""Pydantic schemas package."""
from app.schemas.auth import ChangePasswordRequest, LoginRequest, MessageResponse
from app.schemas.commercial import (
    ConsentRequest,
    CustomerCreate,
    CustomerDetailResponse,
    CustomerPage,
    CustomerResponse,
    CustomerUpdate,
    MessagePreviewRequest,
    MessagePreviewResponse,
    MessageTemplateCreate,
    MessageTemplateResponse,
    MessageTemplateUpdate,
)
from app.schemas.store import StoreCreate, StoreResponse, StoreUpdate, UserStoreUpdate
from app.schemas.user import UserCreate, UserResponse, UserUpdate

__all__ = [
    "ChangePasswordRequest",
    "ConsentRequest",
    "CustomerCreate",
    "CustomerDetailResponse",
    "CustomerPage",
    "CustomerResponse",
    "CustomerUpdate",
    "LoginRequest",
    "MessageResponse",
    "MessagePreviewRequest",
    "MessagePreviewResponse",
    "MessageTemplateCreate",
    "MessageTemplateResponse",
    "MessageTemplateUpdate",
    "StoreCreate",
    "StoreResponse",
    "StoreUpdate",
    "UserCreate",
    "UserResponse",
    "UserStoreUpdate",
    "UserUpdate",
]
