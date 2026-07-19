from fastapi import APIRouter, Request

from grovello.schemas import ApiEnvelope, ApiMeta, DashboardMetric, DashboardOverview

router = APIRouter()


@router.get("/overview", response_model=ApiEnvelope[DashboardOverview])
async def overview(request: Request) -> ApiEnvelope[DashboardOverview]:
    data = DashboardOverview(
        metrics=[
            DashboardMetric(
                key="attributed_revenue", label="Attributed revenue", value="$286,420", delta="+18.4%"
            ),
            DashboardMetric(
                key="open_pipeline", label="Open pipeline", value="$1.24M", delta="63% of target"
            ),
            DashboardMetric(
                key="qualified_leads", label="Qualified leads", value="348", delta="27 need review"
            ),
            DashboardMetric(key="active_runs", label="Active runs", value="23", delta="across 9 workflows"),
        ],
        pending_decisions=2,
        active_runs=23,
        data_notice="Seed response: production data sources are not connected.",
    )
    return ApiEnvelope(data=data, meta=ApiMeta(request_id=request.state.request_id, source="seed"))
