from fastapi import APIRouter, Request

from auth import sso_dto, sso_service
from auth.dto import TokenData
from auth.sso_dto import SUPPORTED_PROVIDERS
from common import erri
from common.resp import Response, ok
from middleware import auth
from user.model import get_user

router = APIRouter(prefix="/auth", tags=["auth-sso"])


def _validate_provider(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise erri.bad_request(f"Unsupported provider: {provider}. Must be one of: {', '.join(SUPPORTED_PROVIDERS)}")


# ---------------------------------------------------------------------------
# SSO Login (unauthenticated)
# ---------------------------------------------------------------------------


@auth.exempt
@router.get("/{provider}/authorize")
async def sso_authorize(provider: str) -> Response:
    """Generate OAuth authorization URL and return it."""
    _validate_provider(provider)
    url = await sso_service.get_authorization_url(provider)
    return ok(data=sso_dto.OAuthAuthorizeResponse(authorization_url=url).model_dump())


@auth.exempt
@router.get("/{provider}/callback")
async def sso_callback(provider: str, code: str, state: str) -> Response:
    """Handle OAuth callback for both login and account linking.

    The state parameter determines the flow:
    - No user_id in state → login/register, returns tokens
    - user_id in state → account linking, returns success message
    """
    _validate_provider(provider)
    token_pair = await sso_service.handle_sso_callback(provider, code, state)
    if token_pair is None:
        # Link flow
        return ok(message=f"{provider.title()} account linked successfully")
    return ok(
        data=TokenData(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            refresh_token_expires_in=token_pair.refresh_token_expires_in,
        ).model_dump()
    )


# ---------------------------------------------------------------------------
# Account Linking (authenticated)
# ---------------------------------------------------------------------------


@router.get("/{provider}/link")
async def sso_link(provider: str, request: Request) -> Response:
    """Start the linking flow for an authenticated user."""
    _validate_provider(provider)
    username = auth.get_username(request)
    user = await get_user(username)
    if not user or user.id is None:
        raise erri.unauthorized("User not found")
    url = await sso_service.get_link_authorization_url(provider, user.id)
    return ok(data=sso_dto.OAuthAuthorizeResponse(authorization_url=url).model_dump())


@router.delete("/{provider}/unlink")
async def sso_unlink(provider: str, request: Request) -> Response:
    """Unlink a provider from the authenticated user."""
    _validate_provider(provider)
    username = auth.get_username(request)
    user = await get_user(username)
    if not user or user.id is None:
        raise erri.unauthorized("User not found")
    await sso_service.unlink_provider(user.id, provider)
    return ok(message=f"{provider.title()} account unlinked successfully")


@router.get("/providers")
async def list_providers(request: Request) -> Response:
    """List linked providers for the authenticated user."""
    username = auth.get_username(request)
    user = await get_user(username)
    if not user or user.id is None:
        raise erri.unauthorized("User not found")
    data = await sso_service.get_linked_providers(user.id)
    return ok(data=data)
