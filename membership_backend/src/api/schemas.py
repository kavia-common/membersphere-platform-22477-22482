"""
Pydantic schemas for all core entities (Org, User, Role, Group, Subscription, Event, Payment, Transaction)
for FastAPI endpoints, validation, and OpenAPI contract.

Each entity: Base, Create, Update, and Output as needed.
"""

from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel, Field, EmailStr, constr

# --- ORG ---

# PUBLIC_INTERFACE
class OrgBase(BaseModel):
    name: str = Field(..., description="Organization name")
    description: Optional[str] = Field(None, description="Description")
    subdomain: Optional[str] = Field(None, description="Subdomain for branded portal")
    primary_color: Optional[str] = Field(None, description="Primary color hex code")
    secondary_color: Optional[str] = Field(None, description="Secondary color hex code")
    accent_color: Optional[str] = Field(None, description="Accent color hex code")
    logo_url: Optional[str] = Field(None, description="URL for logo image")

# PUBLIC_INTERFACE
class OrgCreate(OrgBase):
    pass

# PUBLIC_INTERFACE
class OrgOut(OrgBase):
    id: int
    created_at: datetime

# --- ROLES ---

# PUBLIC_INTERFACE
class RoleBase(BaseModel):
    name: str = Field(..., description="Role name")
    description: Optional[str]

class RoleCreate(RoleBase):
    pass

# PUBLIC_INTERFACE
class RoleOut(RoleBase):
    id: int

# --- USERS ---

# PUBLIC_INTERFACE
class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str] = None
    preferred_language: Optional[str]

class UserCreate(UserBase):
    password: constr(min_length=8)
    org_id: Optional[int] = None  # For onboarding by org-admin
    roles: Optional[List[str]] = Field(default_factory=list)  # role names or IDs
    parent_id: Optional[int] = None

class UserUpdate(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    password: Optional[constr(min_length=8)]
    preferred_language: Optional[str]
    parent_id: Optional[int]

# PUBLIC_INTERFACE
class UserOut(UserBase):
    id: int
    is_active: bool
    org_id: Optional[int]
    roles: List[RoleOut] = Field(default_factory=list)
    groups: List[int] = Field(default_factory=list)
    parent_id: Optional[int]
    children: List[int] = Field(default_factory=list)
    created_at: datetime

# --- GROUP/FAMILY ---

# PUBLIC_INTERFACE
class GroupBase(BaseModel):
    name: str
    description: Optional[str]

class GroupCreate(GroupBase):
    org_id: int
    members: Optional[List[int]] = Field(default_factory=list)

# PUBLIC_INTERFACE
class GroupOut(GroupBase):
    id: int
    org_id: int
    members: List[int] = Field(default_factory=list)

# --- SUBSCRIPTION ---

# PUBLIC_INTERFACE
class SubscriptionBase(BaseModel):
    member_id: int
    start_date: date
    end_date: date
    amount: float
    status: str

class SubscriptionCreate(SubscriptionBase):
    pass

# PUBLIC_INTERFACE
class SubscriptionOut(SubscriptionBase):
    id: int
    payment_history: List["PaymentOut"] = Field(default_factory=list)

# --- PAYMENTS ---

# PUBLIC_INTERFACE
class PaymentBase(BaseModel):
    member_id: int
    amount: float
    payment_date: date
    method: str
    status: str

class PaymentCreate(PaymentBase):
    subscription_id: int

# PUBLIC_INTERFACE
class PaymentOut(PaymentBase):
    id: int
    subscription_id: Optional[int] = None
    reference: Optional[str] = None

# --- EVENTS ---

# PUBLIC_INTERFACE
class EventBase(BaseModel):
    org_id: int
    title: str
    description: Optional[str]
    date: date
    start_time: str
    end_time: str
    location: str
    capacity: Optional[int]
    fee: Optional[float]

class EventCreate(EventBase):
    organizer_id: int

# PUBLIC_INTERFACE
class EventOut(EventBase):
    id: int
    organizer_id: int
    attendees: List[int] = Field(default_factory=list)
    qr_code_url: Optional[str] = None

# --- RSVP ---

class RSVPRequest(BaseModel):
    event_id: int
    status: str

# --- TRANSACTIONS ---

# PUBLIC_INTERFACE
class TransactionBase(BaseModel):
    date: date
    category: str
    description: Optional[str]
    amount: float
    account: str
    transaction_type: str

class TransactionCreate(TransactionBase):
    pass

# PUBLIC_INTERFACE
class TransactionOut(TransactionBase):
    id: int
    created_by: int
    created_at: datetime

# --- MODEL REBUILD for recursive references ---

SubscriptionOut.model_rebuild()
PaymentOut.model_rebuild()
