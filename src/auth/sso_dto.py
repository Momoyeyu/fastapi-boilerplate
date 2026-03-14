from pydantic import BaseModel

SUPPORTED_PROVIDERS = ("google", "github")


class OAuthAuthorizeResponse(BaseModel):
    authorization_url: str


class LinkedProvider(BaseModel):
    provider: str
    email: str | None
    linked_at: str


class LinkedProvidersResponse(BaseModel):
    providers: list[LinkedProvider]
    has_password: bool
