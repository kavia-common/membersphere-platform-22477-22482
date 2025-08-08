"""
Branding endpoints for organization portals: org-level logo and color CRUD.

- Get/set/update branding settings (logo URL, colors, org display name)
- RBAC protected (admins only) and leveraged on subdomain/portal creation.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.models import Org, User
from src.api.schemas import BrandingSettings
from src.api.auth import get_db, get_current_user, rbac_required

router = APIRouter(prefix="/branding", tags=["Branding"])

# PUBLIC_INTERFACE
@router.get("/{org_id}", response_model=BrandingSettings, summary="Get organization branding")
def get_branding(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch branding (logo, color, name) for an organization (admins/members).
    """
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return BrandingSettings(
        org_name=org.name,
        logo_url=org.logo_url,
        primary_color=org.primary_color or "#1976d2",
        secondary_color=org.secondary_color,
        accent_color=org.accent_color,
        subdomain=org.subdomain,
    )

# PUBLIC_INTERFACE
@router.put("/{org_id}", response_model=BrandingSettings, summary="Update org branding", tags=["Branding"])
def update_branding(
    org_id: int,
    branding: BrandingSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    """
    Set branding (logo/colors/name) for an organization (admin only).
    """
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.name = branding.org_name
    org.logo_url = branding.logo_url
    org.primary_color = branding.primary_color
    org.secondary_color = branding.secondary_color
    org.accent_color = branding.accent_color
    org.subdomain = branding.subdomain
    db.commit()
    db.refresh(org)
    return BrandingSettings(
        org_name=org.name,
        logo_url=org.logo_url,
        primary_color=org.primary_color or "#1976d2",
        secondary_color=org.secondary_color,
        accent_color=org.accent_color,
        subdomain=org.subdomain,
    )
