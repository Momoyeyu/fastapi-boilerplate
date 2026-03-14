"""
SSO service — business logic for OAuth2 login via Google and GitHub.

Sections:
1. OAuth client setup
2. OAuth state management (Redis)
3. Provider user info fetching
4. SSO login / account linking
"""

import json
import secrets
from uuid import UUID

from httpx_oauth.clients.github import GitHubOAuth2
from httpx_oauth.clients.google import GoogleOAuth2
from loguru import logger
from uuid6 import uuid7

from auth.dto import TokenPair
from auth.oauth_model import (
    OAuthAccount,
    create_oauth_account,
    delete_oauth_account,
    get_oauth_account,
    get_oauth_accounts_for_user,
)
from auth.service import create_token
from common import erri
from conf.config import settings
from conf.db import AsyncSessionLocal
from conf.redis import get_redis
from tenant.model import Tenant, UserTenant
from user.model import User, get_user_by_email, get_user_by_id

# ---------------------------------------------------------------------------
# 1. OAuth client setup
# ---------------------------------------------------------------------------

_OAUTH_STATE_PREFIX = "oauth_state:"
_OAUTH_STATE_TTL = 600  # 10 minutes


def _get_google_client() -> GoogleOAuth2:
    return GoogleOAuth2(settings.google_client_id, settings.google_client_secret.get_secret_value())


def _get_github_client() -> GitHubOAuth2:
    return GitHubOAuth2(settings.github_client_id, settings.github_client_secret.get_secret_value())


def _get_client(provider: str):
    if provider == "google":
        return _get_google_client()
    elif provider == "github":
        return _get_github_client()
    raise erri.bad_request(f"Unsupported provider: {provider}")


def _get_scopes(provider: str) -> list[str]:
    if provider == "google":
        return ["openid", "email", "profile"]
    elif provider == "github":
        return ["read:user", "user:email"]
    return []


def _callback_url(provider: str, *, link: bool = False) -> str:
    base = settings.oauth_redirect_base_url or f"http://{settings.server_host}:{settings.server_port}"
    suffix = "/link/callback" if link else "/callback"
    return f"{base}/api/v1/auth/{provider}{suffix}"


# ---------------------------------------------------------------------------
# 2. OAuth state management (Redis)
# ---------------------------------------------------------------------------


def _store_state(provider: str, *, user_id: UUID | None = None) -> str:
    state = secrets.token_urlsafe(32)
    data = json.dumps({"provider": provider, "user_id": str(user_id) if user_id else None})
    get_redis().setex(f"{_OAUTH_STATE_PREFIX}{state}", _OAUTH_STATE_TTL, data)
    return state


def _consume_state(state: str) -> dict | None:
    r = get_redis()
    key = f"{_OAUTH_STATE_PREFIX}{state}"
    data = r.get(key)
    if data is None:
        return None
    r.delete(key)
    return json.loads(data)


# ---------------------------------------------------------------------------
# 3. Authorization URL generation
# ---------------------------------------------------------------------------


async def get_authorization_url(provider: str, *, user_id: UUID | None = None, link: bool = False) -> str:
    client = _get_client(provider)
    state = _store_state(provider, user_id=user_id)
    redirect_uri = _callback_url(provider, link=link)
    scopes = _get_scopes(provider)
    url = await client.get_authorization_url(redirect_uri, state=state, scope=scopes)
    return url


# ---------------------------------------------------------------------------
# 4. SSO callback — login or register
# ---------------------------------------------------------------------------


async def _fetch_user_info(provider: str, access_token: str) -> dict:
    """Fetch user info from provider API."""
    import httpx

    if provider == "google":
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "id": data["sub"],
                "email": data.get("email"),
                "email_verified": data.get("email_verified", False),
                "name": data.get("name"),
                "avatar_url": data.get("picture"),
            }
    elif provider == "github":
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            # Get user profile
            resp = await client.get("https://api.github.com/user", headers=headers)
            resp.raise_for_status()
            profile = resp.json()

            # Get verified email
            email_resp = await client.get("https://api.github.com/user/emails", headers=headers)
            email_resp.raise_for_status()
            emails = email_resp.json()
            primary_email = None
            email_verified = False
            for e in emails:
                if e.get("primary") and e.get("verified"):
                    primary_email = e["email"]
                    email_verified = True
                    break

            return {
                "id": str(profile["id"]),
                "email": primary_email,
                "email_verified": email_verified,
                "name": profile.get("name") or profile.get("login"),
                "avatar_url": profile.get("avatar_url"),
            }
    raise erri.bad_request(f"Unsupported provider: {provider}")


async def _create_sso_user_with_tenant(
    *,
    username: str,
    email: str,
    tenant_name: str,
    provider: str,
    provider_user_id: str,
    provider_email: str | None = None,
    provider_username: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """Atomically create user, tenant, user_tenant, and oauth_account in one transaction."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            user = User(username=username, hashed_password=None, email=email)
            session.add(user)
            await session.flush()

            tenant = Tenant(name=tenant_name)
            session.add(tenant)
            await session.flush()

            user_tenant = UserTenant(user_id=user.id, tenant_id=tenant.id, user_role="owner")
            session.add(user_tenant)

            oauth_acc = OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=provider_email,
                provider_username=provider_username,
                avatar_url=avatar_url,
            )
            session.add(oauth_acc)
            await session.flush()

            await session.refresh(user)
    return user


async def handle_sso_callback(provider: str, code: str, state: str) -> TokenPair:
    """Handle the OAuth callback: exchange code, find/create user, issue tokens."""
    # Validate state
    state_data = _consume_state(state)
    if state_data is None:
        raise erri.bad_request("Invalid or expired OAuth state")
    if state_data["provider"] != provider:
        raise erri.bad_request("OAuth state provider mismatch")

    # Exchange code for token
    client = _get_client(provider)
    redirect_uri = _callback_url(provider)
    try:
        oauth2_token = await client.get_access_token(code, redirect_uri)
    except Exception:
        logger.exception(f"Failed to exchange OAuth code for {provider}")
        raise erri.bad_request("Failed to exchange authorization code") from None

    access_token = oauth2_token["access_token"]

    # Fetch user info from provider
    try:
        user_info = await _fetch_user_info(provider, access_token)
    except Exception:
        logger.exception(f"Failed to fetch user info from {provider}")
        raise erri.internal("Failed to fetch user info from provider") from None

    provider_user_id = user_info["id"]
    provider_email = user_info.get("email")
    email_verified = user_info.get("email_verified", False)

    # 1. Check if oauth_account already exists
    oauth_account = await get_oauth_account(provider, provider_user_id)
    if oauth_account:
        user = await get_user_by_id(oauth_account.user_id)
        if not user or user.is_deleted:
            raise erri.unauthorized("User account not found or deactivated")
        return create_token(user)

    # 2. Try to link by email if verified
    if provider_email and email_verified:
        existing_user = await get_user_by_email(provider_email)
        if existing_user and not existing_user.is_deleted and existing_user.is_active:
            await create_oauth_account(
                existing_user.id,
                provider,
                provider_user_id,
                provider_email=provider_email,
                provider_username=user_info.get("name"),
                avatar_url=user_info.get("avatar_url"),
            )
            return create_token(existing_user)

    # 3. Create new user + oauth_account atomically
    if provider_email and not email_verified:
        raise erri.bad_request("Email not verified by provider. Please verify your email first.")

    username = f"user_{uuid7().hex[:12]}"
    tenant_name = f"workspace_{uuid7().hex[:12]}"
    email = provider_email or f"{provider}_{provider_user_id}@oauth.local"

    try:
        user = await _create_sso_user_with_tenant(
            username=username,
            email=email,
            tenant_name=tenant_name,
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=provider_email,
            provider_username=user_info.get("name"),
            avatar_url=user_info.get("avatar_url"),
        )
    except Exception:
        logger.exception("Failed to create user via SSO")
        raise erri.internal("Failed to create user") from None

    return create_token(user)


# ---------------------------------------------------------------------------
# 5. Account linking (authenticated user)
# ---------------------------------------------------------------------------


async def get_link_authorization_url(provider: str, user_id: UUID) -> str:
    """Generate authorization URL for linking a provider to an existing account."""
    # Check if already linked
    accounts = await get_oauth_accounts_for_user(user_id)
    for acc in accounts:
        if acc.provider == provider:
            raise erri.conflict(f"Provider {provider} is already linked")
    return await get_authorization_url(provider, user_id=user_id, link=True)


async def handle_link_callback(provider: str, code: str, state: str, username: str) -> None:
    """Handle the link callback: exchange code, link provider to current user."""
    state_data = _consume_state(state)
    if state_data is None:
        raise erri.bad_request("Invalid or expired OAuth state")
    if state_data["provider"] != provider:
        raise erri.bad_request("OAuth state provider mismatch")

    user_id_str = state_data.get("user_id")
    if not user_id_str:
        raise erri.bad_request("Invalid link state: missing user context")
    user_id = UUID(user_id_str)

    # Verify the user making the request matches the state
    user = await get_user_by_id(user_id)
    if not user or user.username != username:
        raise erri.forbidden("User mismatch in link flow")

    # Check if already linked
    accounts = await get_oauth_accounts_for_user(user_id)
    for acc in accounts:
        if acc.provider == provider:
            raise erri.conflict(f"Provider {provider} is already linked")

    # Exchange code
    client = _get_client(provider)
    redirect_uri = _callback_url(provider, link=True)
    try:
        oauth2_token = await client.get_access_token(code, redirect_uri)
    except Exception:
        raise erri.bad_request("Failed to exchange authorization code") from None

    access_token = oauth2_token["access_token"]
    user_info = await _fetch_user_info(provider, access_token)

    # Check this provider account isn't already linked to someone else
    existing = await get_oauth_account(provider, user_info["id"])
    if existing:
        raise erri.conflict("This provider account is already linked to another user")

    await create_oauth_account(
        user_id,
        provider,
        user_info["id"],
        provider_email=user_info.get("email"),
        provider_username=user_info.get("name"),
        avatar_url=user_info.get("avatar_url"),
    )


async def unlink_provider(user_id: UUID, provider: str) -> None:
    """Unlink a provider from the user. Must retain at least one login method."""
    user = await get_user_by_id(user_id)
    if not user:
        raise erri.not_found("User not found")

    accounts = await get_oauth_accounts_for_user(user_id)
    has_password = user.hashed_password is not None
    linked_count = len(accounts)

    # Must retain at least one login method
    provider_linked = any(a.provider == provider for a in accounts)
    if not provider_linked:
        raise erri.not_found(f"Provider {provider} is not linked")

    if not has_password and linked_count <= 1:
        raise erri.bad_request("Cannot unlink the only login method. Set a password first.")

    await delete_oauth_account(user_id, provider)


async def get_linked_providers(user_id: UUID) -> dict:
    """Get linked providers and password status for a user."""
    user = await get_user_by_id(user_id)
    if not user:
        raise erri.not_found("User not found")

    accounts = await get_oauth_accounts_for_user(user_id)
    providers = [
        {
            "provider": acc.provider,
            "email": acc.provider_email,
            "linked_at": acc.created_at.isoformat() if acc.created_at else None,
        }
        for acc in accounts
    ]
    return {
        "providers": providers,
        "has_password": user.hashed_password is not None,
    }
