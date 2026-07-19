from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from grovello.access import ActorContext, AuthorizedWorkspace, access_directory
from grovello.config import get_settings


async def require_actor(
    x_grovello_dev_subject: Annotated[str | None, Header()] = None,
    x_grovello_dev_session: Annotated[str | None, Header()] = None,
) -> ActorContext:
    settings = get_settings()
    if settings.environment == "production":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC session verification is not configured",
        )
    if not x_grovello_dev_subject or not x_grovello_dev_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Development session is required",
            headers={"WWW-Authenticate": "GrovelloDevelopmentSession"},
        )
    return ActorContext(subject_id=x_grovello_dev_subject, session_id=x_grovello_dev_session)


async def require_workspace_id(x_workspace_id: Annotated[str | None, Header()] = None) -> UUID:
    if not x_workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Workspace-ID is required")
    try:
        return UUID(x_workspace_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Workspace-ID must be a UUID",
        ) from error


async def require_workspace_access(
    actor: Annotated[ActorContext, Depends(require_actor)],
    workspace_id: Annotated[UUID, Depends(require_workspace_id)],
) -> AuthorizedWorkspace:
    return access_directory.authorize(actor, workspace_id)
