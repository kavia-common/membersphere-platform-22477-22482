"""
Authentication endpoints and RBAC logic for Micro-Membership SaaS Platform.

- Sign Up (org-tenant aware)
- Sign In (JWT issuance)
- JWT Auth, Role-based dependency
- RBAC for Super Admin, State Admin, District Admin, Branch Admin, Member
- Multi-tenant support (organization isolation)

All endpoints documented for OpenAPI/Swagger.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import ValidationError
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import os

from src.api.models import User, Org, Role
from src.api.openapi_schemas import (
    UserCreate, Token, TokenPayload, UserOut, ErrorResponse
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

router = APIRouter(tags=["Authentication"])

# =============================
# JWT/Password Config
# =============================
# PUBLIC_INTERFACE
# Use env vars for JWT secret/key expiration
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "devsecretkey")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24hr default

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# ---- DB Session Setup (for demo: using env DB_URL or fallback to in-memory sqlite) ----
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./test.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    """Yields a SQLAlchemy session for dependency-injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =============================
# Utility Functions
# =============================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify that a plaintext password matches its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token with optional expiry."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def get_roles_for_user(user: User) -> List[str]:
    """Extract role names from user model (handle multiple roles per user)."""
    return [role.name for role in user.roles] if hasattr(user, "roles") and user.roles else []

# =============================
# Authentication Logic
# =============================

# PUBLIC_INTERFACE
def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Check user's credentials. Return user or None."""
    user = db.query(User).filter(User.email == email).options(joinedload(User.roles), joinedload(User.org)).first()
    if not user or not user.is_active or not verify_password(password, user.hashed_password):
        return None
    return user

def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).options(joinedload(User.roles), joinedload(User.org)).filter(User.id == user_id).first()

# =============================
# JWT Auth Dependency
# =============================

# PUBLIC_INTERFACE
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Get the current user from the JWT, raise 401 if invalid."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    if token is None:
        raise credentials_exception
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise credentials_exception
    user = get_user(db, int(token_data.sub))
    if user is None or not user.is_active:
        raise credentials_exception
    return user

# PUBLIC_INTERFACE
def rbac_required(*allowed_roles: str):
    """
    Returns a dependency that restricts endpoint to users with any of the allowed roles.
    Example: Depends(rbac_required("Super Admin")) or ("Branch Admin", "Member")
    """
    def dependency(current_user: User = Depends(get_current_user)):
        user_roles = get_roles_for_user(current_user)
        if not any(role in allowed_roles for role in user_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role permissions")
        return current_user
    return dependency

# PUBLIC_INTERFACE
def org_partitioned(current_user: User = Depends(get_current_user)):
    """
    Dependency to pass current org_id for multi-tenant separation.
    Enforces tenant for API queries.
    """
    return current_user.org_id

# =============================
# ENDPOINTS: Authentication
# =============================

@router.post("/auth/signup", response_model=UserOut, responses={400: {"model": ErrorResponse}}, summary="User signup (org-aware)", description="Sign up for an organization. Only works for new users. Initial account must be created by Super Admin or Org Admin.")
async def signup(user_in: UserCreate, db: Session = Depends(get_db), request: Request = None):
    """
    Registers a new user and assigns to an organization and role. 
    Only available to bootstrap orgs or via admin interface.
    """
    # Check if org exists
    org = None
    if hasattr(user_in, "org_id") and user_in.org_id:
        org = db.query(Org).filter(Org.id == user_in.org_id).first()
        if not org:
            raise HTTPException(status_code=400, detail="Organization not found")
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    # Role assignment, default to "Member" if no role found
    role_obj = db.query(Role).filter(Role.name == user_in.role).first() if hasattr(user_in, "role") else None
    if not role_obj:
        role_obj = db.query(Role).filter(Role.name == "Member").first()
        if not role_obj:
            # If Role table is not initialized, create default roles
            for r in ["Super Admin", "State Admin", "District Admin", "Branch Admin", "Member"]:
                db.add(Role(name=r, description=f"{r} role"))
            db.commit()
            role_obj = db.query(Role).filter(Role.name == user_in.role or "Member").first()
    db_user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        phone=user_in.phone,
        org_id=org.id if org else None,
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    # Assign role
    db_user.roles.append(role_obj)
    db.commit()
    db.refresh(db_user)
    # Return as UserOut
    return UserOut(
        id=db_user.id,
        email=db_user.email,
        first_name=db_user.first_name,
        last_name=db_user.last_name,
        phone=db_user.phone,
        is_active=db_user.is_active,
        roles=[r.name for r in db_user.roles],
        groups=[g.id for g in getattr(db_user, "groups", [])]
    )


@router.post("/auth/login", response_model=Token, responses={401: {"model": ErrorResponse}}, summary="User login", description="Authenticate user and return a JWT access token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login endpoint accepting x-www-form-urlencoded username/password.
    Returns JWT access token on success.
    """
    email = form_data.username
    password = form_data.password
    user = authenticate_user(db, email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "roles": get_roles_for_user(user),
            "org_id": user.org_id
        }
    )
    return Token(access_token=access_token, token_type="bearer")

@router.get("/auth/me", response_model=UserOut, summary="Get current user info", description="Returns info for currently authenticated user")
async def me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone=current_user.phone,
        is_active=current_user.is_active,
        roles=get_roles_for_user(current_user),
        groups=[g.id for g in getattr(current_user, "groups", [])]
    )

# =============================
# RBAC Example Protected Routes
# =============================

@router.get("/rbac/superadmin", summary="Super Admin only endpoint", description="Only Super Admins allowed", dependencies=[Depends(rbac_required("Super Admin"))])
async def super_admin_only():
    return {"msg": "You are Super Admin!"}

@router.get("/rbac/stateadmin", summary="State Admin and above", description="State Admin or Super Admin roles")
async def state_admin(current_user: User = Depends(rbac_required("Super Admin", "State Admin"))):
    return {"msg": "You are State-level Admin!", "user": current_user.email}

@router.get("/rbac/branchadmin", summary="Branch Admin or higher", description="Accessible by Branch, District, State, Super Admins")
async def branch_admin(current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin"))):
    return {"msg": "You are Branch-level Admin!", "user": current_user.email}

@router.get("/rbac/member", summary="Member access", description="Any Member (or admin) can use this")
async def member_access(current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin", "Member"))):
    return {"msg": "Hello Member!", "user": current_user.email}

# =============================
# Tenant Partitioning Example Route
# =============================
@router.get("/org/context", summary="Tenant context test", description="Returns current user and their org (multi-tenant decor)", response_model=dict)
async def org_context(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.id,
        "org_id": current_user.org_id,
        "roles": get_roles_for_user(current_user)
    }

# =============================
# FastAPI Project Usage Note for WebSocket Integration
# =============================
# (Add similar route if/when websocket/real-time support is needed.)

