from uuid import UUID

from common import erri
from conf.db import AsyncSessionLocal
from tenant.model import (
    Tenant,
    UserTenant,
    create_tenant,
    create_user_tenant,
    get_tenant,
    get_user_tenant,
    get_user_tenants,
)
from tenant.model import (
    update_tenant as _update_tenant,
)
from user.model import User


async def create_user_with_tenant(
    username: str,
    hashed_password: str,
    email: str,
    tenant_name: str,
    *,
    invitation_code_id: UUID | None = None,
) -> tuple[User, Tenant, UserTenant]:
    """Atomically create a user, a tenant, and assign the user as owner.

    All three inserts happen in a single transaction.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            user = User(
                username=username,
                hashed_password=hashed_password,
                email=email,
                invitation_code_id=invitation_code_id,
            )
            session.add(user)
            await session.flush()

            tenant = Tenant(name=tenant_name)
            session.add(tenant)
            await session.flush()

            user_tenant = UserTenant(user_id=user.id, tenant_id=tenant.id, user_role="owner")
            session.add(user_tenant)
            await session.flush()

            await session.refresh(user)
            await session.refresh(tenant)
            await session.refresh(user_tenant)

        return user, tenant, user_tenant


async def create_tenant_for_user(user_id: UUID, tenant_name: str) -> tuple[Tenant, UserTenant]:
    """Create a new tenant and assign the user as owner.

    Returns:
        A tuple of (Tenant, UserTenant).
    """
    tenant = await create_tenant(tenant_name)
    user_tenant = await create_user_tenant(user_id, tenant.id, user_role="owner")
    return tenant, user_tenant


async def get_tenant_detail(user_id: UUID, tenant_id: UUID) -> Tenant:
    """Get a tenant that the user belongs to."""
    user_tenant = await get_user_tenant(user_id, tenant_id)
    if not user_tenant:
        raise erri.not_found("Not a member of this tenant")

    tenant = await get_tenant(tenant_id)
    if not tenant:
        raise erri.not_found("Tenant not found")
    return tenant


async def update_tenant_by_owner(
    user_id: UUID, tenant_id: UUID, *, name: str | None = None, status: str | None = None
) -> Tenant:
    """Update tenant. Only the owner can update."""
    user_tenant = await get_user_tenant(user_id, tenant_id)
    if not user_tenant:
        raise erri.not_found("Not a member of this tenant")
    if user_tenant.user_role != "owner":
        raise erri.forbidden("Only owner can update tenant")

    tenant = await _update_tenant(tenant_id, name=name, status=status)
    if not tenant:
        raise erri.not_found("Tenant not found")
    return tenant


async def list_tenants_for_user(user_id: UUID) -> list[dict]:
    """List all tenants the user belongs to, with role info."""
    user_tenants = await get_user_tenants(user_id)
    results = []
    for ut in user_tenants:
        tenant = await get_tenant(ut.tenant_id)
        if tenant:
            results.append({"tenant_id": tenant.id, "tenant_name": tenant.name, "user_role": ut.user_role})
    return results
