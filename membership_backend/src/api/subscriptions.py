"""
Subscription management endpoints for Micro-Membership SaaS Platform.

Includes APIs for:
- Assign (create), renew, cancel subscriptions
- Get subscriptions by member/group/org
- Aggregate (by org), filter by status
- Export paid/unpaid members/subscriptions as CSV/Excel
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from src.api.models import Subscription, User
from src.api.schemas import (
    SubscriptionCreate,
    SubscriptionOut,
    APIResponse,
    PaymentOut,
)
from src.api.auth import get_db
import csv
import io

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

# PUBLIC_INTERFACE
@router.post("/", response_model=SubscriptionOut, summary="Assign/Create subscription")
def assign_subscription(
    subscription_in: SubscriptionCreate,
    db: Session = Depends(get_db),
):
    """Assign a subscription to a member."""
    member = db.query(User).filter(User.id == subscription_in.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    sub = Subscription(
        member_id=subscription_in.member_id,
        start_date=subscription_in.start_date,
        end_date=subscription_in.end_date,
        amount=subscription_in.amount,
        status=subscription_in.status or "active"
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return SubscriptionOut(
        id=sub.id,
        member_id=sub.member_id,
        start_date=sub.start_date,
        end_date=sub.end_date,
        amount=sub.amount,
        status=sub.status,
        payment_history=[]
    )

# PUBLIC_INTERFACE
@router.put("/{subscription_id}/renew", response_model=SubscriptionOut, summary="Renew subscription")
def renew_subscription(
    subscription_id: int,
    new_end_date: date,
    db: Session = Depends(get_db),
):
    """Renew a subscription by updating end date and status."""
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.end_date = new_end_date
    sub.status = "active"
    db.commit()
    db.refresh(sub)
    return SubscriptionOut(
        id=sub.id,
        member_id=sub.member_id,
        start_date=sub.start_date,
        end_date=sub.end_date,
        amount=sub.amount,
        status=sub.status,
        payment_history=[p for p in getattr(sub, "payments", [])]
    )

# PUBLIC_INTERFACE
@router.put("/{subscription_id}/cancel", response_model=APIResponse, summary="Cancel subscription")
def cancel_subscription(
    subscription_id: int,
    db: Session = Depends(get_db)
):
    """Cancel a subscription (set status to cancelled)."""
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.status = "cancelled"
    db.commit()
    return APIResponse(success=True, message="Subscription cancelled")

# PUBLIC_INTERFACE
@router.get("/by_member/{member_id}", response_model=List[SubscriptionOut], summary="List subscriptions for member")
def list_subscriptions_by_member(
    member_id: int,
    db: Session = Depends(get_db)
):
    """Get all subscriptions for a particular member."""
    subs = db.query(Subscription).filter(Subscription.member_id == member_id).all()
    result = []
    for s in subs:
        result.append(
            SubscriptionOut(
                id=s.id,
                member_id=s.member_id,
                start_date=s.start_date,
                end_date=s.end_date,
                amount=s.amount,
                status=s.status,
                payment_history=[PaymentOut(
                    id=p.id,
                    member_id=p.member_id,
                    amount=p.amount,
                    payment_date=p.payment_date,
                    method=p.method,
                    status=p.status,
                    subscription_id=p.subscription_id,
                    reference=p.reference,
                ) for p in getattr(s, "payments", [])]
            )
        )
    return result

# PUBLIC_INTERFACE
@router.get("/by_org/{org_id}", response_model=List[SubscriptionOut], summary="List subscriptions for org")
def list_subscriptions_by_org(
    org_id: int,
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """List all subscriptions for an organization, filterable by status."""
    members = db.query(User.id).filter(User.org_id == org_id)
    q = db.query(Subscription).filter(Subscription.member_id.in_(members))
    if status:
        q = q.filter(Subscription.status == status)
    subs = q.all()
    result = []
    for s in subs:
        result.append(
            SubscriptionOut(
                id=s.id,
                member_id=s.member_id,
                start_date=s.start_date,
                end_date=s.end_date,
                amount=s.amount,
                status=s.status,
                payment_history=[
                    PaymentOut(
                        id=p.id,
                        member_id=p.member_id,
                        amount=p.amount,
                        payment_date=p.payment_date,
                        method=p.method,
                        status=p.status,
                        subscription_id=p.subscription_id,
                        reference=p.reference,
                    ) for p in getattr(s, "payments", [])
                ],
            )
        )
    return result

# PUBLIC_INTERFACE
@router.get("/aggregate/org/{org_id}", summary="Aggregate subscription stats (org)", response_model=dict)
def aggregate_subscription_by_org(
    org_id: int,
    db: Session = Depends(get_db)
):
    """Aggregate subscription/payment stats for organization."""
    total_members = db.query(User).filter(User.org_id == org_id).count()
    subs = db.query(Subscription).join(User, Subscription.member_id == User.id).filter(User.org_id == org_id)
    total_subs = subs.count()
    paid_subs = subs.filter(Subscription.status == "active").count()
    overdue_subs = subs.filter(Subscription.status == "overdue").count()
    cancelled_subs = subs.filter(Subscription.status == "cancelled").count()
    return {
        "total_members": total_members,
        "total_subscriptions": total_subs,
        "active_subscriptions": paid_subs,
        "overdue_subscriptions": overdue_subs,
        "cancelled_subscriptions": cancelled_subs,
    }

# PUBLIC_INTERFACE
@router.get("/export", summary="Export members by subscription/payment status", response_class=StreamingResponse)
def export_members_subscription_csv(
    org_id: int,
    status: str = Query(..., description="Subscription status to export (active, overdue, cancelled, pending)"),
    format: str = Query("csv", description="Export format: csv or xlsx"),
    db: Session = Depends(get_db)
):
    """Export paid/unpaid/cancelled members for org as CSV or Excel."""
    members = db.query(User).filter(User.org_id == org_id).all()
    result = []
    for m in members:
        for sub in m.subscriptions:
            if sub.status == status:
                result.append({
                    "Member ID": m.id,
                    "Member Name": f"{m.first_name} {m.last_name}",
                    "Email": m.email,
                    "Subscription Start": sub.start_date,
                    "Subscription End": sub.end_date,
                    "Amount": sub.amount,
                    "Status": sub.status,
                })
    output = io.StringIO()
    if format == "csv":
        writer = csv.DictWriter(output, fieldnames=result[0].keys() if result else ["Member ID", "Member Name", "Email", "Subscription Start", "Subscription End", "Amount", "Status"])
        writer.writeheader()
        for row in result:
            writer.writerow(row)
        output.seek(0)
        headers = {
            "Content-Disposition": f"attachment; filename=subscriptions_{status}.csv"
        }
        return StreamingResponse(output, headers=headers, media_type="text/csv")
    else:
        # Placeholder: Write simple TSV for 'xlsx', or use openpyxl/xlsxwriter in future
        writer = csv.DictWriter(output, fieldnames=result[0].keys() if result else ["Member ID", "Member Name", "Email", "Subscription Start", "Subscription End", "Amount", "Status"], delimiter='\t')
        writer.writeheader()
        for row in result:
            writer.writerow(row)
        output.seek(0)
        headers = {
            "Content-Disposition": f"attachment; filename=subscriptions_{status}.xlsx"
        }
        return StreamingResponse(output, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
