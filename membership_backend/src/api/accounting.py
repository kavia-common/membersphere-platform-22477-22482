"""
Accounting endpoints for managing categorized transactions (income and expenses), with role-based access.
- Record, list, update, and delete financial transactions (categorized)
- List transactions for org, user, date/category filters
- For integration into financial dashboard and export/report features
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from src.api.models import Transaction, User
from src.api.schemas import (
    TransactionCreate,
    TransactionOut,
    APIResponse,
)
from src.api.auth import get_db, get_current_user, rbac_required

router = APIRouter(prefix="/accounting", tags=["Accounting"])

# PUBLIC_INTERFACE
@router.post("/", response_model=TransactionOut, summary="Record transaction", status_code=201)
def record_transaction(
    transaction_in: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    """
    Record a new accounting transaction (income or expense).
    Only Admins (of any level) may record transactions.
    """
    txn = Transaction(
        date=transaction_in.date,
        category=transaction_in.category,
        description=transaction_in.description,
        amount=transaction_in.amount,
        account=transaction_in.account,
        transaction_type=transaction_in.transaction_type,
        created_by=current_user.id,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return TransactionOut(
        id=txn.id,
        date=txn.date,
        category=txn.category,
        description=txn.description,
        amount=txn.amount,
        account=txn.account,
        transaction_type=txn.transaction_type,
        created_by=txn.created_by,
        created_at=txn.created_at,
    )

# PUBLIC_INTERFACE
@router.get("/", response_model=List[TransactionOut], summary="List transactions")
def list_transactions(
    db: Session = Depends(get_db),
    account: Optional[str] = Query(None, description="Filter by account"),
    category: Optional[str] = Query(None, description="Category filter"),
    from_date: Optional[date] = Query(None, description="From date"),
    to_date: Optional[date] = Query(None, description="To date"),
    transaction_type: Optional[str] = Query(None, description="'income' or 'expense'"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin", "Member")),
):
    """
    List all transactions, optionally filter by account, date range, category, type.
    Member sees only their entries. Admins see all.
    """
    q = db.query(Transaction)
    # Members can only see their own transactions (if desired, could be more flexible)
    if "Member" in [r.name if hasattr(r, 'name') else r for r in getattr(current_user, "roles", [])]:
        q = q.filter(Transaction.created_by == current_user.id)
    # Admins can filter by account, date, category, etc.
    if account:
        q = q.filter(Transaction.account == account)
    if category:
        q = q.filter(Transaction.category == category)
    if from_date:
        q = q.filter(Transaction.date >= from_date)
    if to_date:
        q = q.filter(Transaction.date <= to_date)
    if transaction_type:
        q = q.filter(Transaction.transaction_type == transaction_type)
    txns = q.order_by(Transaction.date.desc()).offset(skip).limit(limit).all()
    return [
        TransactionOut(
            id=t.id,
            date=t.date,
            category=t.category,
            description=t.description,
            amount=t.amount,
            account=t.account,
            transaction_type=t.transaction_type,
            created_by=t.created_by,
            created_at=t.created_at,
        )
        for t in txns
    ]

# PUBLIC_INTERFACE
@router.get("/{transaction_id}", response_model=TransactionOut, summary="Get transaction")
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if "Member" in [r.name if hasattr(r, "name") else r for r in getattr(current_user, "roles", [])]:
        if txn.created_by != current_user.id:
            raise HTTPException(status_code=403, detail="Members may only view their own transactions")
    return TransactionOut(
        id=txn.id,
        date=txn.date,
        category=txn.category,
        description=txn.description,
        amount=txn.amount,
        account=txn.account,
        transaction_type=txn.transaction_type,
        created_by=txn.created_by,
        created_at=txn.created_at,
    )

# PUBLIC_INTERFACE
@router.delete("/{transaction_id}", response_model=APIResponse, summary="Delete transaction")
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(txn)
    db.commit()
    return APIResponse(success=True, message="Transaction deleted")

# PUBLIC_INTERFACE
@router.put("/{transaction_id}", response_model=TransactionOut, summary="Update transaction")
def update_transaction(
    transaction_id: int,
    transaction_in: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    for attr, value in transaction_in.model_dump().items():
        setattr(txn, attr, value)
    db.commit()
    db.refresh(txn)
    return TransactionOut(
        id=txn.id,
        date=txn.date,
        category=txn.category,
        description=txn.description,
        amount=txn.amount,
        account=txn.account,
        transaction_type=txn.transaction_type,
        created_by=txn.created_by,
        created_at=txn.created_at,
    )
