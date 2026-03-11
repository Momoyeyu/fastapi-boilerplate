from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from conf.db import AsyncSessionLocal, Base


class Tenant(Base):
    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    status: Mapped[str] = mapped_column(String, default="active")  # active / disabled / suspended
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class UserTenant(Base):
    __tablename__ = "user_tenant"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), index=True)
    user_role: Mapped[str] = mapped_column(String, default="member")  # owner / admin / member
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant"),)


async def create_tenant(name: str) -> Tenant:
    """Create a new tenant."""
    tenant = Tenant(name=name)
    async with AsyncSessionLocal() as session:
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
    return tenant


async def get_tenant(tenant_id: int) -> Tenant | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.id == tenant_id, Tenant.is_deleted == False)  # noqa: E712
        )
        return result.scalars().one_or_none()


async def get_tenant_by_name(name: str) -> Tenant | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.name == name, Tenant.is_deleted == False)  # noqa: E712
        )
        return result.scalars().one_or_none()


async def update_tenant(tenant_id: int, *, name: str | None = None, status: str | None = None) -> Tenant | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.id == tenant_id, Tenant.is_deleted == False)  # noqa: E712
        )
        tenant = result.scalars().one_or_none()
        if not tenant:
            return None

        if name is not None:
            tenant.name = name
        if status is not None:
            tenant.status = status

        tenant.updated_at = datetime.now(UTC)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        return tenant


async def create_user_tenant(user_id: int, tenant_id: int, user_role: str = "member") -> UserTenant:
    """Create a user-tenant association."""
    user_tenant = UserTenant(user_id=user_id, tenant_id=tenant_id, user_role=user_role)
    async with AsyncSessionLocal() as session:
        session.add(user_tenant)
        await session.commit()
        await session.refresh(user_tenant)
    return user_tenant


async def get_user_tenant(user_id: int, tenant_id: int) -> UserTenant | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserTenant).where(
                UserTenant.user_id == user_id,
                UserTenant.tenant_id == tenant_id,
                UserTenant.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalars().one_or_none()


async def get_user_tenants(user_id: int) -> list[UserTenant]:
    """Get all tenants for a user."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserTenant).where(
                UserTenant.user_id == user_id,
                UserTenant.is_deleted == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())
