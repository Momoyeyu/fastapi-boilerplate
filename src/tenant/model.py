from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, select
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from conf.db import AsyncSessionLocal, Base


class Tenant(Base):
    __tablename__ = "tenant"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    status: Mapped[str] = mapped_column(String, default="active")  # active / disabled / suspended
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class UserTenant(Base):
    __tablename__ = "user_tenant"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("user.id"), index=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tenant.id"), index=True)
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


async def get_tenant(tenant_id: UUID) -> Tenant | None:
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


async def update_tenant(tenant_id: UUID, *, name: str | None = None, status: str | None = None) -> Tenant | None:
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


async def create_user_tenant(user_id: UUID, tenant_id: UUID, user_role: str = "member") -> UserTenant:
    """Create a user-tenant association."""
    user_tenant = UserTenant(user_id=user_id, tenant_id=tenant_id, user_role=user_role)
    async with AsyncSessionLocal() as session:
        session.add(user_tenant)
        await session.commit()
        await session.refresh(user_tenant)
    return user_tenant


async def get_user_tenant(user_id: UUID, tenant_id: UUID) -> UserTenant | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserTenant).where(
                UserTenant.user_id == user_id,
                UserTenant.tenant_id == tenant_id,
                UserTenant.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalars().one_or_none()


async def get_user_tenants(user_id: UUID) -> list[UserTenant]:
    """Get all tenants for a user."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserTenant).where(
                UserTenant.user_id == user_id,
                UserTenant.is_deleted == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())


class TenantInvitation(Base):
    __tablename__ = "tenant_invitation"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tenant.id"), index=True)
    email: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[str] = mapped_column(String, default="member")  # member / admin
    invited_by: Mapped[UUID] = mapped_column(Uuid, ForeignKey("user.id"))
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending / accepted
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


async def create_tenant_invitation(
    tenant_id: UUID, email: str, role: str, invited_by: UUID, token: str, expires_at: datetime
) -> TenantInvitation:
    invitation = TenantInvitation(
        tenant_id=tenant_id,
        email=email.lower(),
        role=role,
        invited_by=invited_by,
        token=token,
        expires_at=expires_at,
    )
    async with AsyncSessionLocal() as session:
        session.add(invitation)
        await session.commit()
        await session.refresh(invitation)
    return invitation


async def get_invitation(invitation_id: UUID) -> TenantInvitation | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(TenantInvitation).where(TenantInvitation.id == invitation_id))
        return result.scalars().one_or_none()


async def get_invitation_by_token(token: str) -> TenantInvitation | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TenantInvitation).where(
                TenantInvitation.token == token,
                TenantInvitation.status == "pending",
            )
        )
        return result.scalars().one_or_none()


async def get_pending_invitations(tenant_id: UUID) -> list[TenantInvitation]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TenantInvitation)
            .where(TenantInvitation.tenant_id == tenant_id, TenantInvitation.status == "pending")
            .order_by(TenantInvitation.created_at.desc())
        )
        return list(result.scalars().all())


async def update_invitation_status(invitation_id: UUID, status: str) -> TenantInvitation | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(TenantInvitation).where(TenantInvitation.id == invitation_id))
        invitation = result.scalars().one_or_none()
        if not invitation:
            return None
        invitation.status = status
        invitation.updated_at = datetime.now(UTC)
        session.add(invitation)
        await session.commit()
        await session.refresh(invitation)
        return invitation


async def get_pending_invitation_by_email_and_tenant(email: str, tenant_id: UUID) -> TenantInvitation | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TenantInvitation).where(
                TenantInvitation.email == email.lower(),
                TenantInvitation.tenant_id == tenant_id,
                TenantInvitation.status == "pending",
            )
        )
        return result.scalars().one_or_none()
