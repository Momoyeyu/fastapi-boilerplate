from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

from middleware.auth import _EXEMPT_ENDPOINT_ATTR


def setup_openapi(app: FastAPI) -> None:
    """Configure custom OpenAPI schema with OAuth2 for Swagger UI."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # Add OAuth2 Password Flow security scheme
        openapi_schema.setdefault("components", {})
        openapi_schema["components"]["securitySchemes"] = {
            "OAuth2PasswordBearer": {
                "type": "oauth2",
                "flows": {
                    "password": {
                        "tokenUrl": "/auth/login",
                        "scopes": {},
                    }
                },
            }
        }

        # Add security requirement to non-exempt routes
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            if getattr(route.endpoint, _EXEMPT_ENDPOINT_ATTR, False):
                continue
            # Add security to this route's operations
            path = openapi_schema["paths"].get(route.path, {})
            for method in route.methods or []:
                method_lower = method.lower()
                if method_lower in path:
                    path[method_lower]["security"] = [{"OAuth2PasswordBearer": []}]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
