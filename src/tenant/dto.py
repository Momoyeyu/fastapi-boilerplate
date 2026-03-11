from uuid import UUID

from pydantic import BaseModel


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
