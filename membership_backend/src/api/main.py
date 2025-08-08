from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import router as auth_router
from src.api.membership import router as membership_router
from src.api.openapi_schemas import openapi_tags

from src.api.subscriptions import router as subscription_router
from src.api.payments import router as payment_router

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

# Mount authentication and RBAC endpoints
app.include_router(auth_router)
# Mount users, groups (families), org CRUD endpoints
app.include_router(membership_router)
# Mount subscription endpoints
app.include_router(subscription_router)
# Mount payment endpoints
app.include_router(payment_router)

@app.get("/", tags=["Misc"])
def health_check():
    """Health check endpoint for system uptime monitoring."""
    return {"message": "Healthy"}

