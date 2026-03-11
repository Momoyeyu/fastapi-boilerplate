from pydantic import BaseModel


class TenantCreateRequest(BaseModel):
    name: str


class TenantUpdateRequest(BaseModel):
    name: str | None = None
    status: str | None = None


class TenantResponse(BaseModel):
    id: int
    name: str
    status: str


class UserTenantResponse(BaseModel):
    tenant_id: int
    tenant_name: str
    user_role: str
