from typing import Annotated

from fastapi import Header, HTTPException, status


async def require_workspace(x_workspace_id: Annotated[str | None, Header()] = None) -> str:
    if not x_workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Workspace-ID is required")
    return x_workspace_id
