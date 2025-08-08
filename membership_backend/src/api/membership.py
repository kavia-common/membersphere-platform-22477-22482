"""
CRUD endpoints for Users, Groups (Families), and Organizations 
with admin assignment, batch import, and hierarchical filtering.

Includes:
- User CRUD (with batch import, admin filters)
- Group (Family) CRUD
- Organization CRUD
- Assign/revoke admin role to user
- Integration with RBAC/tenant partitioning for security

OpenAPI tagged and response schemas set for Swagger.
"""
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from src.api.models import User, Group, Org, Role
from src.api.schemas import (
    UserCreate, UserUpdate, UserOut, GroupCreate, GroupOut, OrgCreate, OrgOut, RoleOut
)
from src.api.auth import get_db, hash_password
from src.api.openapi_schemas import ErrorResponse, APIResponse

router = APIRouter(prefix="/membership", tags=["Users", "Groups", "Organizations"])

# ---------- ORGANIZATION CRUD ----------

# PUBLIC_INTERFACE
@router.post("/orgs/", response_model=OrgOut, responses={400: {"model": ErrorResponse}}, summary="Create organization", tags=["Organizations"])
def create_org(org_in: OrgCreate, db: Session = Depends(get_db)):
    """
    Create a new organization.
    """
    if db.query(Org).filter(Org.name == org_in.name).first():
        raise HTTPException(status_code=400, detail="Organization with this name already exists")
    org = Org(**org_in.model_dump())
    db.add(org)
    db.commit()
    db.refresh(org)
    return org

# PUBLIC_INTERFACE
@router.get("/orgs/", response_model=List[OrgOut], summary="List organizations", tags=["Organizations"])
def list_orgs(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """
    List all organizations. (Super Admin only recommended)
    """
    return db.query(Org).offset(skip).limit(limit).all()

# PUBLIC_INTERFACE
@router.get("/orgs/{org_id}", response_model=OrgOut, summary="Get organization", tags=["Organizations"])
def get_org(org_id: int, db: Session = Depends(get_db)):
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org

# PUBLIC_INTERFACE
@router.put("/orgs/{org_id}", response_model=OrgOut, summary="Update organization", tags=["Organizations"])
def update_org(org_id: int, org_in: OrgCreate, db: Session = Depends(get_db)):
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    for k, v in org_in.model_dump().items():
        setattr(org, k, v)
    db.commit()
    db.refresh(org)
    return org

# PUBLIC_INTERFACE
@router.delete("/orgs/{org_id}", response_model=APIResponse, summary="Delete organization", tags=["Organizations"])
def delete_org(org_id: int, db: Session = Depends(get_db)):
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    db.delete(org)
    db.commit()
    return APIResponse(success=True, message="Deleted.")

# ---------- USER CRUD & BATCH IMPORT ----------

# PUBLIC_INTERFACE
@router.post("/users/", response_model=UserOut, responses={400: {"model": ErrorResponse}}, summary="Create user", tags=["Users"])
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Create a user; specify org_id and roles as a list of role names.
    """
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    org = db.query(Org).filter(Org.id == user_in.org_id).first() if user_in.org_id else None
    role_objs = []
    if user_in.roles:
        for r in user_in.roles:
            obj = db.query(Role).filter(Role.name == r).first()
            if obj:
                role_objs.append(obj)
    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        phone=user_in.phone,
        preferred_language=getattr(user_in, "preferred_language", None),
        org_id=user_in.org_id if org else None,
        is_active=True,
        parent_id=user_in.parent_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # assign roles
    user.roles = role_objs or []
    db.commit()
    db.refresh(user)
    return UserOut(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        is_active=user.is_active,
        org_id=user.org_id,
        roles=[RoleOut(id=r.id, name=r.name, description=r.description) for r in user.roles],
        groups=[g.id for g in user.groups],
        parent_id=user.parent_id,
        children=[c.id for c in user.children],
        created_at=user.created_at
    )

# PUBLIC_INTERFACE
@router.get("/users/", response_model=List[UserOut], summary="List/filter users", tags=["Users"])
def list_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
    org_id: Optional[int] = Query(None),
    admin_level: Optional[str] = Query(None, description="Role filter (Super Admin, State Admin, District Admin, Branch Admin, Member)"),
    q: Optional[str] = Query(None, description="Free text user search"),
):
    qset = db.query(User)
    if org_id:
        qset = qset.filter(User.org_id == org_id)
    if admin_level:
        # Filter users by role
        qset = qset.join(User.roles).filter(Role.name == admin_level)
    if q:
        qset = qset.filter(
            (User.first_name.ilike(f"%{q}%")) |
            (User.last_name.ilike(f"%{q}%")) |
            (User.email.ilike(f"%{q}%"))
        )
    users = qset.offset(skip).limit(limit).options(joinedload(User.roles), joinedload(User.groups)).all()
    return [
        UserOut(
            id=u.id,
            email=u.email,
            first_name=u.first_name,
            last_name=u.last_name,
            phone=u.phone,
            is_active=u.is_active,
            org_id=u.org_id,
            roles=[RoleOut(id=r.id, name=r.name, description=r.description) for r in u.roles],
            groups=[g.id for g in u.groups],
            parent_id=u.parent_id,
            children=[c.id for c in u.children] if hasattr(u, "children") else [],
            created_at=u.created_at
        )
        for u in users
    ]

# PUBLIC_INTERFACE
@router.get("/users/{user_id}", response_model=UserOut, summary="Get user", tags=["Users"])
def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).options(joinedload(User.roles), joinedload(User.groups)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        is_active=user.is_active,
        org_id=user.org_id,
        roles=[RoleOut(id=r.id, name=r.name, description=r.description) for r in user.roles],
        groups=[g.id for g in user.groups],
        parent_id=user.parent_id,
        children=[c.id for c in user.children] if hasattr(user, "children") else [],
        created_at=user.created_at
    )

# PUBLIC_INTERFACE
@router.put("/users/{user_id}", response_model=UserOut, summary="Update user", tags=["Users"])
def update_user(user_id: int, user_in: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update = user_in.model_dump(exclude_unset=True)
    for k, v in update.items():
        if k == "password" and v:
            user.hashed_password = hash_password(v)
        elif k != "password":
            setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return get_user_by_id(user.id, db)

# PUBLIC_INTERFACE
@router.delete("/users/{user_id}", response_model=APIResponse, summary="Delete user", tags=["Users"])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return APIResponse(success=True, message="User deleted")

# PUBLIC_INTERFACE
@router.post("/users/batch_import", response_model=Dict[str, int], summary="Batch import users", description="Batch create users, returns count of successful and failed inserts.", tags=["Users"])
def batch_import_users(
    users: List[UserCreate] = Body(...),
    db: Session = Depends(get_db),
):
    inserted = 0
    failed = 0
    for user_in in users:
        try:
            if db.query(User).filter(User.email == user_in.email).first():
                failed += 1
                continue
            org = db.query(Org).filter(Org.id == user_in.org_id).first() if user_in.org_id else None
            role_objs = []
            if user_in.roles:
                for r in user_in.roles:
                    obj = db.query(Role).filter(Role.name == r).first()
                    if obj:
                        role_objs.append(obj)
            user = User(
                email=user_in.email,
                hashed_password=hash_password(user_in.password),
                first_name=user_in.first_name,
                last_name=user_in.last_name,
                phone=user_in.phone,
                preferred_language=getattr(user_in, "preferred_language", None),
                org_id=user_in.org_id if org else None,
                is_active=True,
                parent_id=user_in.parent_id
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            user.roles = role_objs or []
            db.commit()
            inserted += 1
        except Exception:
            db.rollback()
            failed += 1
    return {"inserted": inserted, "failed": failed}

# PUBLIC_INTERFACE
@router.post("/users/{user_id}/assign_admin", response_model=UserOut, summary="Assign admin role", description="Assign an admin role to a user (by role name)", tags=["Users"])
def assign_admin_role(
    user_id: int,
    role_name: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role not in user.roles:
        user.roles.append(role)
        db.commit()
        db.refresh(user)
    return get_user_by_id(user_id, db)

# PUBLIC_INTERFACE
@router.post("/users/{user_id}/remove_admin", response_model=UserOut, summary="Revoke admin role", description="Remove an admin role from a user (by role name)", tags=["Users"])
def remove_admin_role(
    user_id: int,
    role_name: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role or role not in user.roles:
        raise HTTPException(status_code=404, detail="Role not assigned to this user")
    user.roles.remove(role)
    db.commit()
    db.refresh(user)
    return get_user_by_id(user_id, db)

# ---------- GROUP/FAMILY CRUD ----------

# PUBLIC_INTERFACE
@router.post("/groups/", response_model=GroupOut, summary="Create group", tags=["Groups"])
def create_group(group_in: GroupCreate, db: Session = Depends(get_db)):
    org = db.query(Org).filter(Org.id == group_in.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    group = Group(
        name=group_in.name,
        description=group_in.description,
        org_id=group_in.org_id
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    # add initial members if provided
    if group_in.members:
        members = db.query(User).filter(User.id.in_(group_in.members)).all()
        group.members = members
        db.commit()
        db.refresh(group)
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        org_id=group.org_id,
        members=[u.id for u in group.members]
    )

# PUBLIC_INTERFACE
@router.get("/groups/", response_model=List[GroupOut], summary="List groups", tags=["Groups"])
def list_groups(
    db: Session = Depends(get_db),
    org_id: Optional[int] = Query(None, description="Filter by organization"),
    skip: int = 0,
    limit: int = 50,
):
    qset = db.query(Group)
    if org_id:
        qset = qset.filter(Group.org_id == org_id)
    groups = qset.offset(skip).limit(limit).options(joinedload(Group.members)).all()
    return [
        GroupOut(
            id=g.id,
            name=g.name,
            description=g.description,
            org_id=g.org_id,
            members=[u.id for u in g.members]
        ) for g in groups
    ]


# PUBLIC_INTERFACE
@router.get("/groups/{group_id}", response_model=GroupOut, summary="Get group", tags=["Groups"])
def get_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).options(joinedload(Group.members)).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        org_id=group.org_id,
        members=[u.id for u in group.members]
    )

# PUBLIC_INTERFACE
@router.put("/groups/{group_id}", response_model=GroupOut, summary="Update group", tags=["Groups"])
def update_group(group_id: int, group_in: GroupCreate, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    group.name = group_in.name
    group.description = group_in.description
    group.org_id = group_in.org_id
    # update members
    if group_in.members is not None:
        members = db.query(User).filter(User.id.in_(group_in.members)).all()
        group.members = members
    db.commit()
    db.refresh(group)
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        org_id=group.org_id,
        members=[u.id for u in group.members]
    )

# PUBLIC_INTERFACE
@router.delete("/groups/{group_id}", response_model=APIResponse, summary="Delete group", tags=["Groups"])
def delete_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(group)
    db.commit()
    return APIResponse(success=True, message="Group deleted")
