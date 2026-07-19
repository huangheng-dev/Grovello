from fastapi import APIRouter

from grovello.api.routes import dashboard, system, workspaces

api_router = APIRouter()
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
