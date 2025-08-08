"""
SQLAlchemy ORM models for the Micro-Membership SaaS Platform.
Defines Org, User, Role, Group (Family), Subscription, Event, Payment, Transaction and their relationships.

Conventions:
- Composite and secondary tables used for many-to-many (user<->groups, user<->roles, event<->user)
- Indexes for fast querying on user/org/group memberships, event participation, and subscriptions.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Float,
    Boolean,
    Date,
    ForeignKey,
    Enum,
    Table,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, backref, declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

# --- Association Tables for Many-to-Many ---

user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id', ondelete="CASCADE"), primary_key=True),
    Index("ix_user_roles_user_id_role_id", "user_id", "role_id", unique=True)
)

user_groups = Table(
    'user_groups',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    Column('group_id', Integer, ForeignKey('groups.id', ondelete="CASCADE"), primary_key=True),
    Index("ix_user_groups_user_id_group_id", "user_id", "group_id", unique=True)
)

event_attendees = Table(
    'event_attendees',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    Column('event_id', Integer, ForeignKey('events.id', ondelete="CASCADE"), primary_key=True),
    Index("ix_event_attendees_user_id_event_id", "event_id", "user_id", unique=True)
)

# --- ENUMs ---

class SubscriptionStatusEnum(str, enum.Enum):
    active = "active"
    pending = "pending"
    overdue = "overdue"
    cancelled = "cancelled"

class PaymentStatusEnum(str, enum.Enum):
    success = "success"
    pending = "pending"
    failed = "failed"

class TransactionTypeEnum(str, enum.Enum):
    income = "income"
    expense = "expense"

class RSVPStatusEnum(str, enum.Enum):
    going = "going"
    maybe = "maybe"
    not_going = "not_going"

# --- MODELS ---

class Org(Base):
    __tablename__ = "orgs"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    description = Column(String(256))
    subdomain = Column(String(64), unique=True, index=True)
    primary_color = Column(String(12))
    secondary_color = Column(String(12))
    accent_color = Column(String(12))
    logo_url = Column(String(256))
    created_at = Column(DateTime, default=func.now())

    # Relationships
    users = relationship("User", back_populates="org", cascade="all, delete", passive_deletes=True)
    groups = relationship("Group", back_populates="org", cascade="all, delete", passive_deletes=True)
    events = relationship("Event", back_populates="org", cascade="all, delete", passive_deletes=True)

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String(32), unique=True, nullable=False)
    description = Column(String(256))

    users = relationship("User", secondary=user_roles, back_populates="roles")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("orgs.id", ondelete="SET NULL"), index=True)
    email = Column(String(128), unique=True, index=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    first_name = Column(String(64), nullable=False)
    last_name = Column(String(64), nullable=False)
    phone = Column(String(32))
    is_active = Column(Boolean, default=True)
    preferred_language = Column(String(8))
    created_at = Column(DateTime, default=func.now())

    # Hierarchy pointers (for multi-level admin/member tree)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    children = relationship("User", backref=backref("parent", remote_side=[id]))

    # Relationships
    org = relationship("Org", back_populates="users")
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    groups = relationship("Group", secondary=user_groups, back_populates="members")
    subscriptions = relationship("Subscription", back_populates="member", cascade="all, delete", passive_deletes=True)
    payments = relationship("Payment", back_populates="member", cascade="all, delete", passive_deletes=True)
    events_attending = relationship("Event", secondary=event_attendees, back_populates="attendees")
    transactions = relationship("Transaction", back_populates="created_by_user")

    __table_args__ = (
        Index("ix_users_org_id", "org_id"),
        Index("ix_users_parent_id", "parent_id"),
    )

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    name = Column(String(64), nullable=False)
    description = Column(String(256))

    org = relationship("Org", back_populates="groups")
    members = relationship("User", secondary=user_groups, back_populates="groups")

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_group_org_name"),
        Index("ix_group_org_id", "org_id"),
    )

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(Enum(SubscriptionStatusEnum), nullable=False, index=True, default=SubscriptionStatusEnum.active)

    member = relationship("User", back_populates="subscriptions")
    payments = relationship("Payment", back_populates="subscription", cascade="all, delete", passive_deletes=True)

    __table_args__ = (
        Index("ix_subscriptions_member_id", "member_id"),
        Index("ix_subscriptions_status", "status"),
    )

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), index=True)
    amount = Column(Float, nullable=False)
    payment_date = Column(Date, nullable=False)
    method = Column(String(32))
    status = Column(Enum(PaymentStatusEnum), nullable=False, default=PaymentStatusEnum.success)
    reference = Column(String(128))

    member = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payments")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    title = Column(String(128), nullable=False)
    description = Column(String(256))
    date = Column(Date, nullable=False)
    start_time = Column(String(8))
    end_time = Column(String(8))
    location = Column(String(128))
    capacity = Column(Integer)
    fee = Column(Float)
    organizer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    qr_code_url = Column(String(256))

    org = relationship("Org", back_populates="events")
    organizer = relationship("User", foreign_keys=[organizer_id])
    attendees = relationship("User", secondary=event_attendees, back_populates="events_attending")

    __table_args__ = (
        Index("ix_events_org_id", "org_id"),
        Index("ix_events_organizer_id", "organizer_id"),
    )

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    category = Column(String(64), nullable=False)
    description = Column(String(256))
    amount = Column(Float, nullable=False)
    account = Column(String(64))
    transaction_type = Column(Enum(TransactionTypeEnum), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at = Column(DateTime, default=func.now())

    created_by_user = relationship("User", back_populates="transactions")
    # Transactions can be related to Org, Payments, Events for further extension

# Index suggestions for rapid search & reporting
Index("ix_payments_member_id", Payment.member_id)
Index("ix_payments_subscription_id", Payment.subscription_id)
Index("ix_payments_status", Payment.status)
Index("ix_events_date", Event.date)
Index("ix_transactions_date", Transaction.date)

# Pydantic models are in schemas.py; for further business logic add methods to models as needed.
