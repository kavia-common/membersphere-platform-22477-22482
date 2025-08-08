from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import router as auth_router
from src.api.membership import router as membership_router
from src.api.openapi_schemas import openapi_tags
from src.api.subscriptions import router as subscriptions_router
from src.api.payments import router as payments_router
from src.api.events import router as events_router
from src.api.qrcodes import router as qrcodes_router
from src.api.accounting import router as accounting_router
from src.api.reports import router as reports_router
from src.api.branding import router as branding_router
from src.api.settings import router as settings_router
from src.api.i18n import router as i18n_router

# Ensure all routers listed in src/api/ are registered and exposed.

app = FastAPI(
    title="Micro-Membership SaaS Platform Backend",
    description="REST API for membership, RBAC, event, accounting, and tenant management (Super/State/District/Branch Admin, Member).",
    version="0.1.0",
    openapi_tags=openapi_tags
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all App Routers - Full API Exposure for Frontend
app.include_router(auth_router)
app.include_router(membership_router)
app.include_router(subscriptions_router)
app.include_router(payments_router)
app.include_router(events_router)
app.include_router(qrcodes_router)
app.include_router(accounting_router)
app.include_router(reports_router)
app.include_router(branding_router)
app.include_router(settings_router)
app.include_router(i18n_router)

@app.get("/", tags=["Misc"])
def health_check():
    """Health check endpoint for system uptime monitoring."""
    return {"message": "Healthy"}
