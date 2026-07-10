from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from api.config import api_keys, bot_api_keys
from api.service import get_user_role
from core import auth as core_auth

security = HTTPBasic(auto_error=False)


@dataclass(frozen=True)
class Actor:
    channel: str  # "bot" | "user"
    username: str
    role: str


def get_actor(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_alucolux_username: Optional[str] = Header(None, alias="X-ALUCOLUX-Username"),
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
) -> Actor:
    """
    Bot Key（ALUCOLUX_BOT_API_KEY）：无需用户名，API 始终返回 public + internal。
    普通 Key：需 X-ALUCOLUX-Username，按 users.json 角色过滤 internal。
    """
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_key")

    if x_api_key in bot_api_keys():
        return Actor(channel="bot", username="bot", role=core_auth.ROLE_ADMIN)

    keys = api_keys()
    if not keys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="api_key_not_configured",
        )
    if x_api_key not in keys:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_key")

    username = (x_alucolux_username or "").strip()
    if not username and credentials is not None:
        username = credentials.username.strip()

    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="username_required")

    role = get_user_role(username)
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_not_found")

    if credentials is not None and credentials.password:
        from core.paths import USERS_PATH

        verified = core_auth.authenticate(USERS_PATH, username, credentials.password)
        if verified is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    return Actor(channel="user", username=username, role=role)
