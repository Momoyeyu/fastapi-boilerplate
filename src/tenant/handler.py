from uuid import UUID

from fastapi import APIRouter, Request

from common import erri
from common.resp import Response, ok
from middleware import auth
from tenant import dto, service
from tenant import model as tenant_model
from user.model import get_user

router = APIRouter(prefix="/tenant", tags=["tenant"])


async def _get_user_id(request: Request) -> UUID:
    username = auth.get_username(request)
    user = await get_user(username)
    if not user or user.id is None:
        raise erri.unauthorized("User not found")
    return user.id


@router.post("")
async def create_tenant(request: Request, body: dto.TenantCreateRequest) -> Response:
    """Create a new tenant. The current user becomes the owner."""
    user_id = await _get_user_id(request)
    tenant, _ = await service.create_tenant_for_user(user_id, body.name)
    return ok(
        data=dto.TenantResponse(
            id=tenant.id,
            name=tenant.name,
            status=tenant.status,
        ).model_dump()
    )


@router.get("")
async def list_tenants(request: Request) -> Response:
    """List all tenants the current user belongs to."""
    user_id = await _get_user_id(request)
    tenants = await service.list_tenants_for_user(user_id)
    return ok(data=[dto.UserTenantResponse(**t).model_dump() for t in tenants])


@router.get("/{tenant_id}")
async def get_tenant(request: Request, tenant_id: UUID) -> Response:
    """Get tenant details. User must be a member."""
    user_id = await _get_user_id(request)
    tenant = await service.get_tenant_detail(user_id, tenant_id)
    return ok(
        data=dto.TenantResponse(
            id=tenant.id,
            name=tenant.name,
            status=tenant.status,
        ).model_dump()
    )


@router.put("/{tenant_id}")
async def update_tenant(request: Request, tenant_id: UUID, body: dto.TenantUpdateRequest) -> Response:
    """Update a tenant. Only the owner can update."""
    user_id = await _get_user_id(request)
    tenant = await service.update_tenant_by_owner(user_id, tenant_id, name=body.name, status=body.status)
    return ok(
        data=dto.TenantResponse(
            id=tenant.id,
            name=tenant.name,
            status=tenant.status,
        ).model_dump()
    )


@router.post("/{tenant_id}/invite")
async def invite_to_tenant(request: Request, tenant_id: UUID, body: dto.TenantInviteRequest) -> Response:
    """Invite a user to join the tenant by email. Only owner or admin can service."""
    user_id = await _get_user_id(request)
    result = await service.invite_user_to_tenant(user_id, tenant_id, body.email, body.role)
    return ok(data=result)


@router.delete("/{tenant_id}/invitations/{invitation_id}")
async def cancel_invitation(request: Request, tenant_id: UUID, invitation_id: UUID) -> Response:
    """Cancel a pending invitation. Only owner or admin can cancel."""
    user_id = await _get_user_id(request)
    await service.cancel_invitation(user_id, tenant_id, invitation_id)
    return ok(message="Invitation cancelled")


@router.get("/{tenant_id}/invitations")
async def list_invitations(request: Request, tenant_id: UUID) -> Response:
    """List pending invitations for a tenant. Only owner or admin can view."""
    user_id = await _get_user_id(request)
    user_tenant = await tenant_model.get_user_tenant(user_id, tenant_id)
    if not user_tenant:
        raise erri.not_found("Not a member of this tenant")
    if user_tenant.user_role not in ("owner", "admin"):
        raise erri.forbidden("Only owner or admin can view invitations")
    invitations = await tenant_model.get_pending_invitations(tenant_id)
    return ok(
        data=[
            dto.TenantInvitationResponse(
                id=inv.id,
                email=inv.email,
                role=inv.role,
                status=inv.status,
                expires_at=inv.expires_at,
                created_at=inv.created_at,
            ).model_dump()
            for inv in invitations
        ]
    )
