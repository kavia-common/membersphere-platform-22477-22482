"""
Reporting endpoints for exporting, summarizing, and serving data for dashboards and charts.
- Download transactions as CSV/Excel
- Aggregate/summarize data for dashboard charts (e.g., monthly totals, categories)
- For organization admins, RBAC protected
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Optional
from datetime import date, datetime

from src.api.models import Transaction, User
from src.api.auth import get_db, rbac_required
import csv
import io

router = APIRouter(prefix="/reports", tags=["Accounting", "Exports", "Reports"])

# PUBLIC_INTERFACE
@router.get("/transactions/export", summary="Export transactions as CSV/Excel", response_class=StreamingResponse)
def export_transactions(
    account: Optional[str] = Query(None, description="Filter by account"),
    category: Optional[str] = Query(None, description="Filter by category"),
    transaction_type: Optional[str] = Query(None, description="'income' or 'expense'"),
    from_date: Optional[date] = Query(None, description="From date"),
    to_date: Optional[date] = Query(None, description="To date"),
    format: str = Query("csv", description="csv or xlsx"),
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    """
    Download all transactions as CSV (or Excel TSV). Admin protection.
    """
    q = db.query(Transaction)
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
    txns = q.order_by(Transaction.date.desc()).all()
    rows = []
    for t in txns:
        rows.append({
            "Transaction ID": t.id,
            "Date": t.date,
            "Category": t.category,
            "Description": t.description,
            "Amount": t.amount,
            "Account": t.account,
            "Type": t.transaction_type,
            "Created By": t.created_by,
            "Created At": t.created_at,
        })
    output = io.StringIO()
    if format == "csv":
        writer = csv.DictWriter(output, fieldnames=rows[0].keys() if rows else [
            "Transaction ID", "Date", "Category", "Description", "Amount", "Account", "Type", "Created By", "Created At"
        ])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        output.seek(0)
        headers = {
            "Content-Disposition": "attachment; filename=transactions.csv"
        }
        return StreamingResponse(output, headers=headers, media_type="text/csv")
    else:
        # Use TSV for xlsx for now
        writer = csv.DictWriter(output, fieldnames=rows[0].keys() if rows else [
            "Transaction ID", "Date", "Category", "Description", "Amount", "Account", "Type", "Created By", "Created At"
        ], delimiter="\t")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        output.seek(0)
        headers = {
            "Content-Disposition": "attachment; filename=transactions.xlsx"
        }
        return StreamingResponse(output, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# PUBLIC_INTERFACE
@router.get("/transactions/chart-data/category", summary="Chart: totals by category")
def transactions_by_category_chart(
    year: Optional[int] = Query(None, description="Year"),
    month: Optional[int] = Query(None, description="Month (optional)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    """
    Returns sum of income and expenses by category for all (optionally by month/year) for charting.
    """
    q = db.query(
        Transaction.category,
        Transaction.transaction_type,
        func.sum(Transaction.amount).label("total")
    )
    if year:
        q = q.filter(extract("year", Transaction.date) == year)
    if month:
        q = q.filter(extract("month", Transaction.date) == month)
    q = q.group_by(Transaction.category, Transaction.transaction_type)
    results = q.all()
    # Structure for frontend: {category: {income: x, expense: y}}
    data = {}
    for row in results:
        cat = row.category
        if cat not in data:
            data[cat] = {"income": 0, "expense": 0}
        data[cat][row.transaction_type] = row.total
    return data

# PUBLIC_INTERFACE
@router.get("/transactions/chart-data/monthly", summary="Chart: monthly totals")
def transactions_monthly_totals_chart(
    year: Optional[int] = Query(None, description="Year (defaults to current year)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    """
    Returns totals (by month) for income and expenses during a year.
    """
    if not year:
        year = datetime.now().year
    q = db.query(
        extract("month", Transaction.date).label("month"),
        Transaction.transaction_type,
        func.sum(Transaction.amount).label("total")
    ).filter(extract("year", Transaction.date) == year
    ).group_by(
        extract("month", Transaction.date),
        Transaction.transaction_type
    ).order_by("month")
    summary = {}
    for row in q:
        mo = int(row.month)
        if mo not in summary:
            summary[mo] = {"income": 0, "expense": 0}
        summary[mo][row.transaction_type] = row.total
    return summary

# PUBLIC_INTERFACE
@router.get("/transactions/chart-data/summary", summary="Chart: summary totals")
def transactions_summary_chart(
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    """
    Returns overall totals for income and expense (for dashboard donut/pie).
    """
    total_income = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(Transaction.transaction_type == "income").scalar() or 0
    total_expense = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(Transaction.transaction_type == "expense").scalar() or 0
    return {
        "income": total_income,
        "expense": total_expense,
        "net": total_income - total_expense
    }
