"""Identify the person from Easy Auth headers, or the local development user."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from app.config import AppSettings


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    display_name: str


def require_user(request: Request, settings: AppSettings) -> AuthenticatedUser:
    principal_id = request.headers.get("x-ms-client-principal-id", "").strip()
    principal_name = request.headers.get("x-ms-client-principal-name", "").strip()
    if principal_id:
        return AuthenticatedUser(principal_id, principal_name or principal_id)
    if settings.app_env == "local":
        return AuthenticatedUser(settings.local_user_id, settings.local_user_name)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required through App Service Easy Auth.")
