"""
Portal settings endpoint for org-level configuration. Manages UX features/preferences per tenant.

- Get/set/update org portal settings (future use: landing page, feature flags)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any

from src.api.schemas import APIResponse
from src.api.auth import get_db, rbac_required
from src.api.models import User

router = APIRouter(prefix="/settings", tags=["Settings"])

# Simulates a table/col for settings per org (use JSONB or extra table in real prod)
ORG_SETTINGS_STORE = {}

# PUBLIC_INTERFACE
@router.get("/{org_id}", summary="Get portal settings", response_model=Dict[str, Any])
def get_settings(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    """
    Fetch org-wide portal settings. Extend as needed for customizable features.
    """
    return ORG_SETTINGS_STORE.get(org_id, {})

# PUBLIC_INTERFACE
@router.put("/{org_id}", summary="Update portal settings", response_model=APIResponse)
def update_settings(
    org_id: int,
    settings: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    """
    Update/set portal settings per organization.
    """
    ORG_SETTINGS_STORE[org_id] = settings
    return APIResponse(success=True, message="Settings updated", data=ORG_SETTINGS_STORE[org_id])
