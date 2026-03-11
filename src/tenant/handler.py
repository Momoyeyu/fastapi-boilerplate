from fastapi import APIRouter, Request

from common import erri
from common.resp import Response, ok
from middleware import auth
from tenant import dto, service
from user.model import get_user

router = APIRouter(prefix="/tenant", tags=["tenant"])


async def _get_user_id(request: Request) -> int:
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
async def get_tenant(request: Request, tenant_id: int) -> Response:
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
async def update_tenant(request: Request, tenant_id: int, body: dto.TenantUpdateRequest) -> Response:
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
