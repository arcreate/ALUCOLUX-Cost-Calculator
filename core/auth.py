"""
用户认证与角色权限（应用层）。

给非程序员的理解方式
--------------------
- 每个登录用户有一个「角色」：管理员 / 高级用户 / 普通用户。
- 角色决定能看到哪些界面、能否改颜色库、能否看完整报告等。
- 账号与密码哈希保存在服务器「数据/users.json」，不进入 git。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROLE_ADMIN = "admin"
ROLE_ADVANCED = "advanced"
ROLE_BASIC = "basic"

VALID_ROLES = {ROLE_ADMIN, ROLE_ADVANCED, ROLE_BASIC}

# 权限点 → 允许的角色集合
PERMISSIONS: Dict[str, Set[str]] = {
    "vars_edit": {ROLE_ADMIN},
    "config_import": {ROLE_ADMIN},
    "config_export": {ROLE_ADMIN},
    "save_default": {ROLE_ADMIN},
    "restore_default": {ROLE_ADMIN, ROLE_ADVANCED, ROLE_BASIC},
    "report_full": {ROLE_ADMIN, ROLE_ADVANCED},
    "report_export": {ROLE_ADMIN, ROLE_ADVANCED},
    "interactive_report": {ROLE_ADMIN, ROLE_ADVANCED},
    "quote_summary": {ROLE_ADMIN, ROLE_ADVANCED, ROLE_BASIC},
    "color_csv_import": {ROLE_ADMIN},
    "color_csv_export": {ROLE_ADMIN},
    "color_add": {ROLE_ADMIN, ROLE_ADVANCED},
    "color_table_edit": {ROLE_ADMIN, ROLE_ADVANCED},
    "color_delete": {ROLE_ADMIN},
    "calc_library_save": {ROLE_ADMIN, ROLE_ADVANCED},
    "calc_library_view": {ROLE_ADMIN, ROLE_ADVANCED},
    "calc_library_delete": {ROLE_ADMIN, ROLE_ADVANCED},
    "optimizer": {ROLE_ADMIN, ROLE_ADVANCED},
    "user_manage": {ROLE_ADMIN},
}

ROLE_LABELS_ZH = {
    ROLE_ADMIN: "管理员",
    ROLE_ADVANCED: "高级用户",
    ROLE_BASIC: "普通用户",
}

ROLE_LABELS_EN = {
    ROLE_ADMIN: "Administrator",
    ROLE_ADVANCED: "Advanced user",
    ROLE_BASIC: "Basic user",
}

_PBKDF2_ITERATIONS = 600_000


class AuthError(Exception):
    """认证或权限相关错误。"""


def auth_disabled() -> bool:
    """便携/本地调试可设 ALUCOLUX_AUTH_DISABLED=1 跳过登录（视为管理员）。"""
    return os.environ.get("ALUCOLUX_AUTH_DISABLED", "").strip().lower() in ("1", "true", "yes")


def can(role: str, permission: str) -> bool:
    allowed = PERMISSIONS.get(permission, set())
    return role in allowed


def require_permission(role: str, permission: str) -> None:
    if not can(role, permission):
        raise AuthError(f"permission_denied:{permission}")


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${base64.b64encode(salt).decode('ascii')}${base64.b64encode(digest).decode('ascii')}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations_s, salt_b64, digest_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iterations_s)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _load_store(users_path: Path) -> Dict[str, Any]:
    if not users_path.is_file():
        return {"users": []}
    try:
        data = json.loads(users_path.read_text(encoding="utf-8"))
        if not isinstance(data.get("users"), list):
            return {"users": []}
        return data
    except (json.JSONDecodeError, OSError):
        return {"users": []}


def _save_store(users_path: Path, data: Dict[str, Any]) -> None:
    users_path.parent.mkdir(parents=True, exist_ok=True)
    users_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_initial_admin(users_path: Path, initial_password: Optional[str] = None) -> bool:
    """
    若 users.json 不存在或为空，创建默认管理员账号 admin。
    返回 True 表示本次新建了初始账号。
    """
    if users_path.is_file():
        store = _load_store(users_path)
        if store.get("users"):
            return False
    pwd = initial_password or os.environ.get("ALUCOLUX_INITIAL_ADMIN_PASSWORD", "").strip() or "changeme"
    store = {
        "users": [
            {
                "username": "admin",
                "role": ROLE_ADMIN,
                "password_hash": hash_password(pwd),
            }
        ]
    }
    _save_store(users_path, store)
    return True


def list_users(users_path: Path) -> List[Dict[str, str]]:
    store = _load_store(users_path)
    out: List[Dict[str, str]] = []
    for u in store.get("users", []):
        if isinstance(u, dict) and u.get("username"):
            out.append({"username": str(u["username"]), "role": str(u.get("role", ROLE_BASIC))})
    return out


def get_user_role(users_path: Path, username: str) -> Optional[str]:
    for u in _load_store(users_path).get("users", []):
        if str(u.get("username", "")) == username:
            role = str(u.get("role", ROLE_BASIC))
            return role if role in VALID_ROLES else ROLE_BASIC
    return None


def authenticate(users_path: Path, username: str, password: str) -> Optional[str]:
    username = username.strip()
    password = password.strip()
    if not username or not password:
        return None
    for u in _load_store(users_path).get("users", []):
        if str(u.get("username", "")) != username:
            continue
        if verify_password(password, str(u.get("password_hash", ""))):
            role = str(u.get("role", ROLE_BASIC))
            return role if role in VALID_ROLES else ROLE_BASIC
    return None


def add_user(users_path: Path, username: str, password: str, role: str) -> None:
    username = username.strip()
    if not username:
        raise AuthError("username_empty")
    if role not in VALID_ROLES:
        raise AuthError("invalid_role")
    store = _load_store(users_path)
    for u in store.get("users", []):
        if str(u.get("username", "")).lower() == username.lower():
            raise AuthError("username_exists")
    store.setdefault("users", []).append(
        {"username": username, "role": role, "password_hash": hash_password(password)}
    )
    _save_store(users_path, store)


def reset_user_password(users_path: Path, username: str, new_password: str) -> None:
    username = username.strip()
    store = _load_store(users_path)
    found = False
    for u in store.get("users", []):
        if str(u.get("username", "")) == username:
            u["password_hash"] = hash_password(new_password)
            found = True
            break
    if not found:
        raise AuthError("user_not_found")
    _save_store(users_path, store)


def set_user_role(users_path: Path, username: str, new_role: str) -> None:
    """修改已有用户角色（不可导致系统无管理员）。"""
    username = username.strip()
    if new_role not in VALID_ROLES:
        raise AuthError("invalid_role")
    store = _load_store(users_path)
    users = store.get("users", [])
    target = None
    for u in users:
        if str(u.get("username", "")) == username:
            target = u
            break
    if target is None:
        raise AuthError("user_not_found")
    old_role = str(target.get("role", ROLE_BASIC))
    if old_role == new_role:
        return
    if old_role == ROLE_ADMIN and new_role != ROLE_ADMIN:
        other_admins = sum(
            1 for u in users if str(u.get("role")) == ROLE_ADMIN and str(u.get("username", "")) != username
        )
        if other_admins < 1:
            raise AuthError("last_admin")
    target["role"] = new_role
    _save_store(users_path, store)


def delete_user(users_path: Path, username: str, *, acting_username: str) -> None:
    username = username.strip()
    if username == acting_username:
        raise AuthError("cannot_delete_self")
    store = _load_store(users_path)
    users = store.get("users", [])
    new_users = [u for u in users if str(u.get("username", "")) != username]
    if len(new_users) == len(users):
        raise AuthError("user_not_found")
    if not any(str(u.get("role")) == ROLE_ADMIN for u in new_users):
        raise AuthError("last_admin")
    store["users"] = new_users
    _save_store(users_path, store)
