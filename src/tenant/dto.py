from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class TenantCreateRequest(BaseModel):
    name: str


class TenantUpdateRequest(BaseModel):
    name: str | None = None
    status: str | None = None


class TenantResponse(BaseModel):
    id: UUID
    name: str
    status: str


class UserTenantResponse(BaseModel):
    tenant_id: UUID
    tenant_name: str
    user_role: str


class TenantInviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"


class TenantInvitationResponse(BaseModel):
    id: UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
