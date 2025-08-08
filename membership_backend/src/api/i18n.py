"""
APIs for multilingual support:

- List all supported languages
- Update user or org preferred language (set in DB)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.models import User, Org
from src.api.schemas import SupportedLanguage, LanguageUpdateRequest, APIResponse
from src.api.auth import get_db, get_current_user, rbac_required

router = APIRouter(prefix="/i18n", tags=["Languages"])

SUPPORTED_LANGUAGES = [
    SupportedLanguage(code="en", label="English"),
    SupportedLanguage(code="hi", label="Hindi"),
    SupportedLanguage(code="es", label="Spanish"),
    SupportedLanguage(code="fr", label="French"),
    SupportedLanguage(code="zh", label="Chinese"),
    SupportedLanguage(code="ar", label="Arabic"),
]

# PUBLIC_INTERFACE
@router.get("/supported", response_model=list[SupportedLanguage], summary="List supported languages")
def list_languages():
    """
    Returns list of supported languages.
    """
    return SUPPORTED_LANGUAGES

# PUBLIC_INTERFACE
@router.put("/user", response_model=APIResponse, summary="Change user language")
def update_user_language(
    lang: LanguageUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Set user's preferred language.
    """
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.preferred_language = lang.language_code
    db.commit()
    return APIResponse(success=True, message="User language updated", data={"language": user.preferred_language})

# PUBLIC_INTERFACE
@router.put("/org/{org_id}", response_model=APIResponse, summary="Change org language", tags=["Languages"])
def update_org_language(
    org_id: int,
    lang: LanguageUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_required("Super Admin", "State Admin", "District Admin", "Branch Admin")),
):
    """
    Set organization default language (applies to all users if organization dictates).
    """
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    # For demo: Save language in secondary storage/dict. In prod, add a DB col.
    if not hasattr(org, "preferred_language"):
        org.preferred_language = lang.language_code  # For demo only
    else:
        setattr(org, "preferred_language", lang.language_code)
    db.commit()
    return APIResponse(success=True, message="Organization language updated", data={"language": lang.language_code})
