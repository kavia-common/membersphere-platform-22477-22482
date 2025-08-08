""" 
OpenAPI-compatible Pydantic schemas and endpoint contracts for the Membership SaaS Platform.
This module defines all REST API schemas for authentication, roles, user/group management,
subscriptions, payments, events, CSV/Excel exports, accounting, branding, and language features.

This file is the single source of truth for data models used in the backend and for frontend-backend communication.
"""

from typing import List, Optional, Dict, Any
from datetime import date
from pydantic import BaseModel, Field, EmailStr, constr

# ----------------------------------------
# PUBLIC_INTERFACE
class Token(BaseModel):
    """
    Access and Refresh token response schema.
    """
    access_token: str = Field(..., description="JWT Access token")
    refresh_token: Optional[str] = Field(None, description="JWT Refresh token")
    token_type: str = Field("bearer", description="The token type, always 'bearer'.")

# ----------------------------------------
# PUBLIC_INTERFACE
class TokenPayload(BaseModel):
    """
    JWT token payload/basic claims schema.
    """
    sub: str = Field(..., description="The subject identifier (usually the user ID).")
    exp: int = Field(..., description="Expiration timestamp (unix epoch).")
    roles: List[str] = Field(..., description="Roles assigned to the user.")

# ==== User & Authentication Schemas ====

# ----------------------------------------
# PUBLIC_INTERFACE
class UserBase(BaseModel):
    """
    Base fields for a user.
    """
    email: EmailStr = Field(..., description="User email address")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    phone: Optional[str] = Field(None, description="Phone number")

# ----------------------------------------
# PUBLIC_INTERFACE
class UserCreate(UserBase):
    """
    Request schema to create a user.
    """
    password: constr(min_length=8) = Field(..., description="User password (min. 8 chars)")
    role: str = Field(..., description="Role for the user")

# ----------------------------------------
# PUBLIC_INTERFACE
class UserUpdate(BaseModel):
    """
    Schema for updating user profile.
    """
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    password: Optional[constr(min_length=8)]

# ----------------------------------------
# PUBLIC_INTERFACE
class UserOut(UserBase):
    """
    Output User schema with additional fields.
    """
    id: int = Field(..., description="User identifier")
    is_active: bool = Field(..., description="Active user")
    roles: List[str] = Field(..., description="Assigned roles")
    groups: List[int] = Field([], description="Groups the user belongs to")

# ----------------------------------------
# PUBLIC_INTERFACE
class LoginRequest(BaseModel):
    """
    Login request schema.
    """
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="User password")

# ----------------------------------------
# PUBLIC_INTERFACE
class ChangePasswordRequest(BaseModel):
    """
    Request to change password.
    """
    current_password: str = Field(..., description="Current password")
    new_password: constr(min_length=8) = Field(..., description="New password")

# ----------------------------------------
# PUBLIC_INTERFACE
class GroupBase(BaseModel):
    """
    Group (e.g., Family or Household) base schema.
    """
    name: str = Field(..., description="Group name")
    description: Optional[str] = Field(None, description="Description or notes")

# ----------------------------------------
# PUBLIC_INTERFACE
class GroupCreate(GroupBase):
    pass

# ----------------------------------------
# PUBLIC_INTERFACE
class GroupOut(GroupBase):
    id: int
    members: List[int] = Field([], description="User IDs of the group members")

# ==== Role Hierarchy ====

# ----------------------------------------
# PUBLIC_INTERFACE
class Role(BaseModel):
    """
    Role definition, possible values: Super Admin, State Admin, District Admin, Branch Admin, Member
    """
    name: str = Field(..., description="Role name")
    description: Optional[str]

# ==== Subscription & Payment ====

# ----------------------------------------
# PUBLIC_INTERFACE
class SubscriptionBase(BaseModel):
    """
    Subscription base schema.
    """
    member_id: int = Field(..., description="User ID of the subscribing member")
    start_date: date = Field(..., description="Subscription start date")
    end_date: date = Field(..., description="Subscription end date")
    amount: float = Field(..., description="Amount for the subscription")
    status: str = Field(..., description="'active', 'pending', 'overdue', 'cancelled'")

# ----------------------------------------
# PUBLIC_INTERFACE
class SubscriptionCreate(SubscriptionBase):
    pass

# ----------------------------------------
# PUBLIC_INTERFACE
class SubscriptionOut(SubscriptionBase):
    id: int
    payment_history: List['PaymentOut'] = Field([], description="List of payment records")

# ----------------------------------------
# PUBLIC_INTERFACE
class PaymentBase(BaseModel):
    """
    Base schema for recording payment.
    """
    member_id: int
    amount: float
    payment_date: date
    method: str = Field(..., description="Payment method, e.g., card, cash, bank transfer")
    status: str = Field(..., description="'success', 'pending', 'failed'")

# ----------------------------------------
# PUBLIC_INTERFACE
class PaymentCreate(PaymentBase):
    pass

# ----------------------------------------
# PUBLIC_INTERFACE
class PaymentOut(PaymentBase):
    id: int
    reference: Optional[str] = Field(None, description="Reference/transaction ID")

# ==== Event Management ====

# ----------------------------------------
# PUBLIC_INTERFACE
class EventBase(BaseModel):
    """
    Event base details.
    """
    title: str
    description: Optional[str]
    date: date
    start_time: str = Field(..., description="Event start time in HH:MM format")
    end_time: str = Field(..., description="Event end time in HH:MM format")
    location: str
    capacity: Optional[int] = Field(None, description="Max participants")
    fee: Optional[float] = Field(None, description="Optional event fee")

# ----------------------------------------
# PUBLIC_INTERFACE
class EventCreate(EventBase):
    pass

# ----------------------------------------
# PUBLIC_INTERFACE
class EventOut(EventBase):
    id: int
    organizer_id: int
    attendees: List[int] = Field([], description="User IDs of attendees")
    qr_code_url: Optional[str] = Field(None, description="QR code URL for check-in")

# ----------------------------------------
# PUBLIC_INTERFACE
class RSVPRequest(BaseModel):
    """
    RSVP to event.
    """
    event_id: int
    status: str = Field(..., description="'going', 'maybe', 'not_going'")

# ==== Export Features (CSV/Excel) ====

# ----------------------------------------
# PUBLIC_INTERFACE
class ExportRequest(BaseModel):
    """
    Request parameters for data export endpoints.
    """
    resource: str = Field(..., description="Resource to export, e.g., 'members', 'payments'")
    format: str = Field(..., description="File format: 'csv' or 'xlsx'")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filtering options")

# ==== Accounting ====

# ----------------------------------------
# PUBLIC_INTERFACE
class TransactionBase(BaseModel):
    """
    Base schema for an accounting transaction.
    """
    date: date
    category: str
    description: Optional[str]
    amount: float
    account: str
    transaction_type: str = Field(..., description="'income' or 'expense'")

# ----------------------------------------
# PUBLIC_INTERFACE
class TransactionCreate(TransactionBase):
    pass

# ----------------------------------------
# PUBLIC_INTERFACE
class TransactionOut(TransactionBase):
    id: int
    created_by: int

# ==== Organization Branding ====

# ----------------------------------------
# PUBLIC_INTERFACE
class BrandingSettings(BaseModel):
    """
    Organization branding settings.
    """
    org_name: str = Field(..., description="Organization display name")
    logo_url: Optional[str] = Field(None, description="URL to organization logo image")
    primary_color: str = Field(..., description="Primary color hex code")
    secondary_color: Optional[str] = Field(None, description="Secondary color hex code")
    accent_color: Optional[str] = Field(None, description="Accent color hex code")
    subdomain: Optional[str] = Field(None, description="Subdomain for branded portal")

# ==== i18n / Language Support ====

# ----------------------------------------
# PUBLIC_INTERFACE
class SupportedLanguage(BaseModel):
    """
    Supported application languages.
    """
    code: str = Field(..., description="Language code (ISO 639-1), e.g., 'en', 'es', 'hi'")
    label: str = Field(..., description="Display name of the language")

# ----------------------------------------
# PUBLIC_INTERFACE
class LanguageUpdateRequest(BaseModel):
    """
    Change preferred language for user or organization.
    """
    language_code: str = Field(..., description="Selected language code")

# ==== Misc / Common ====

# ----------------------------------------
# PUBLIC_INTERFACE
class APIResponse(BaseModel):
    """
    Standard API response wrapper.
    """
    success: bool = Field(..., description="Request was successful")
    message: Optional[str] = Field(None, description="A human-readable message")
    data: Optional[Any] = Field(None, description="Payload")

# ----------------------------------------
# PUBLIC_INTERFACE
class ErrorResponse(BaseModel):
    """
    Error response wrapper.
    """
    detail: str = Field(..., description="Error details")

# Pydantic recursion workaround
SubscriptionOut.model_rebuild()
PaymentOut.model_rebuild()

# ---- Endpoint Contracts: Tag Mapping (for OpenAPI tags) ----
openapi_tags = [
    {"name": "Authentication", "description": "User login, logout, token management and password."},
    {"name": "Users", "description": "CRUD and management of system users."},
    {"name": "Groups", "description": "Family or household group management."},
    {"name": "Roles", "description": "Role hierarchy and access management."},
    {"name": "Subscriptions", "description": "Recurring payment and subscription management."},
    {"name": "Payments", "description": "Payment records, history, gateways."},
    {"name": "Events", "description": "Event listing, creation, RSVP, QR check-in."},
    {"name": "Exports", "description": "Export members, payments, transaction data."},
    {"name": "Accounting", "description": "Income, expenses, transactions for organizations."},
    {"name": "Branding", "description": "Branded portal and visual settings for orgs."},
    {"name": "Languages", "description": "Multilingual support, language switching."},
]

# ---- Endpoint Description Examples ----
# These schemas should be referenced by FastAPI route decorators for response_model, request_model, and OpenAPI docs.

# Example use (in routes):
#   @router.post("/auth/login", response_model=Token, tags=["Authentication"])
#   async def login(data: LoginRequest): ...

#   @router.get("/users/me", response_model=UserOut, tags=["Users"])
#   async def me(): ...

