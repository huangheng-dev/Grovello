from fastapi import APIRouter, Request

from grovello.schemas import ApiEnvelope, ApiMeta, WorkspaceSummary

router = APIRouter()


@router.get("", response_model=ApiEnvelope[list[WorkspaceSummary]])
async def list_workspaces(request: Request) -> ApiEnvelope[list[WorkspaceSummary]]:
    data = [
        WorkspaceSummary(
            id="00000000-0000-4000-8000-000000000001",
            slug="northstar-industrial",
            name="Northstar Industrial",
            default_locale="en",
            timezone="Asia/Shanghai",
        ),
        WorkspaceSummary(
            id="00000000-0000-4000-8000-000000000002",
            slug="global-sandbox",
            name="Global Sandbox",
            default_locale="en",
            timezone="UTC",
        ),
    ]
    return ApiEnvelope(data=data, meta=ApiMeta(request_id=request.state.request_id, source="seed"))
