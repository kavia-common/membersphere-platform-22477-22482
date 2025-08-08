"""
Payment management endpoints for Micro-Membership SaaS Platform.

Includes APIs for:
- Record payment for member/subscription
- Mark/update payment status
- List payment history for member, org
- Aggregate payment stats
- Export payments as CSV/Excel
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from src.api.models import Payment, User, Subscription
from src.api.schemas import (
    PaymentCreate,
    PaymentOut,
    APIResponse,
)
from src.api.auth import get_db
import csv
import io

router = APIRouter(prefix="/payments", tags=["Payments"])

# PUBLIC_INTERFACE
@router.post("/", response_model=PaymentOut, summary="Record payment")
def record_payment(
    payment_in: PaymentCreate,
    db: Session = Depends(get_db),
):
    """Record a payment for a member's subscription."""
    member = db.query(User).filter(User.id == payment_in.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    subscription = db.query(Subscription).filter(Subscription.id == payment_in.subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    payment = Payment(
        member_id=payment_in.member_id,
        subscription_id=payment_in.subscription_id,
        amount=payment_in.amount,
        payment_date=payment_in.payment_date,
        method=payment_in.method,
        status=payment_in.status or "success",
        reference=getattr(payment_in, "reference", None),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return PaymentOut(
        id=payment.id,
        member_id=payment.member_id,
        amount=payment.amount,
        payment_date=payment.payment_date,
        method=payment.method,
        status=payment.status,
        subscription_id=payment.subscription_id,
        reference=payment.reference,
    )

# PUBLIC_INTERFACE
@router.put("/{payment_id}/status", response_model=APIResponse, summary="Update payment status")
def update_payment_status(
    payment_id: int,
    new_status: str = Query(..., description="New status: success, failed, pending"),
    db: Session = Depends(get_db)
):
    """Update/mark the payment status."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    payment.status = new_status
    db.commit()
    return APIResponse(success=True, message="Payment status updated")

# PUBLIC_INTERFACE
@router.get("/by_member/{member_id}", response_model=List[PaymentOut], summary="Payment history for member")
def payment_history_member(
    member_id: int,
    db: Session = Depends(get_db),
):
    """List all payments for a specific member."""
    qset = db.query(Payment).filter(Payment.member_id == member_id).all()
    return [
        PaymentOut(
            id=p.id,
            member_id=p.member_id,
            amount=p.amount,
            payment_date=p.payment_date,
            method=p.method,
            status=p.status,
            subscription_id=p.subscription_id,
            reference=p.reference,
        ) for p in qset
    ]

# PUBLIC_INTERFACE
@router.get("/by_subscription/{subscription_id}", response_model=List[PaymentOut], summary="List payments for a subscription")
def payment_history_subscription(
    subscription_id: int,
    db: Session = Depends(get_db)
):
    """List all payments for a single subscription."""
    qset = db.query(Payment).filter(Payment.subscription_id == subscription_id).all()
    return [
        PaymentOut(
            id=p.id,
            member_id=p.member_id,
            amount=p.amount,
            payment_date=p.payment_date,
            method=p.method,
            status=p.status,
            subscription_id=p.subscription_id,
            reference=p.reference,
        ) for p in qset
    ]

# PUBLIC_INTERFACE
@router.get("/by_org/{org_id}", response_model=List[PaymentOut], summary="List all payments for org")
def payment_history_by_org(
    org_id: int,
    db: Session = Depends(get_db),
):
    """List all payments by org (all members)."""
    member_ids = [u.id for u in db.query(User).filter(User.org_id == org_id).all()]
    qset = db.query(Payment).filter(Payment.member_id.in_(member_ids)).all()
    return [
        PaymentOut(
            id=p.id,
            member_id=p.member_id,
            amount=p.amount,
            payment_date=p.payment_date,
            method=p.method,
            status=p.status,
            subscription_id=p.subscription_id,
            reference=p.reference,
        ) for p in qset
    ]

# PUBLIC_INTERFACE
@router.get("/aggregate/org/{org_id}", summary="Aggregate payment stats (org)", response_model=dict)
def aggregate_payment_by_org(
    org_id: int,
    db: Session = Depends(get_db)
):
    """Aggregate payment stats for an organization."""
    member_ids = [u.id for u in db.query(User).filter(User.org_id == org_id).all()]
    total_payments = db.query(Payment).filter(Payment.member_id.in_(member_ids)).count()
    total_amount = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.member_id.in_(member_ids)).scalar() or 0
    paid = db.query(Payment).filter(Payment.member_id.in_(member_ids), Payment.status == "success").count()
    pending = db.query(Payment).filter(Payment.member_id.in_(member_ids), Payment.status == "pending").count()
    failed = db.query(Payment).filter(Payment.member_id.in_(member_ids), Payment.status == "failed").count()
    return {
        "total_payments": total_payments,
        "total_amount": total_amount,
        "num_paid": paid,
        "num_pending": pending,
        "num_failed": failed,
    }

# PUBLIC_INTERFACE
@router.get("/export", summary="Export payments by org as CSV/Excel", response_class=StreamingResponse)
def export_payments_csv(
    org_id: int,
    status: Optional[str] = Query(None, description="Filter by payment status"),
    format: str = Query("csv", description="csv or xlsx"),
    db: Session = Depends(get_db),
):
    """Export payments for org as CSV or Excel."""
    member_ids = [u.id for u in db.query(User).filter(User.org_id == org_id).all()]
    qset = db.query(Payment).filter(Payment.member_id.in_(member_ids))
    if status:
        qset = qset.filter(Payment.status == status)
    rows = []
    for p in qset:
        rows.append({
            "Payment ID": p.id,
            "Member ID": p.member_id,
            "Amount": p.amount,
            "Date": p.payment_date,
            "Method": p.method,
            "Status": p.status,
            "Subscription ID": p.subscription_id,
            "Reference": p.reference,
        })
    output = io.StringIO()
    if format == "csv":
        writer = csv.DictWriter(output, fieldnames=rows[0].keys() if rows else ["Payment ID", "Member ID", "Amount", "Date", "Method", "Status", "Subscription ID", "Reference"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        output.seek(0)
        headers = {
            "Content-Disposition": f"attachment; filename=payments_{org_id}.csv"
        }
        return StreamingResponse(output, headers=headers, media_type="text/csv")
    else:
        # For xlsx, use TSV as a simple fallback
        writer = csv.DictWriter(output, fieldnames=rows[0].keys() if rows else ["Payment ID", "Member ID", "Amount", "Date", "Method", "Status", "Subscription ID", "Reference"], delimiter='\t')
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        output.seek(0)
        headers = {
            "Content-Disposition": f"attachment; filename=payments_{org_id}.xlsx"
        }
        return StreamingResponse(output, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
