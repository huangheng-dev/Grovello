from fastapi import APIRouter

from grovello.api.routes import (
    assets,
    business_imports,
    business_truth,
    dashboard,
    system,
    workspace_onboarding,
    workspaces,
)

api_router = APIRouter()
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(
    business_truth.router,
    prefix="/business-truth",
    tags=["business-truth"],
)
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(
    workspace_onboarding.router,
    prefix="/workspace-onboarding",
    tags=["workspace-onboarding"],
)
api_router.include_router(
    business_imports.router,
    prefix="/import-jobs",
    tags=["business-imports"],
)
