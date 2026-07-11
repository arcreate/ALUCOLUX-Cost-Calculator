"""
生成 Hermes / 企微 Bot 一键配置 ZIP 包（仅管理员使用）。

Bot 模式：使用 ALUCOLUX_BOT_API_KEY，无需企微 userid 映射；
API 返回 public + internal，由 Skill 管控对用户展示的内容。
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from core.paths import app_root, bundle_root

# Bot/Agent 默认走 HTTP + 已备案域名（避免 sspc 子域未备案被阿里云拦截；Agent VPS 亦免 TLS 握手问题）
DEFAULT_API_BASE = "http://alucolux.shenliwen.cc"
BUNDLE_VERSION = "2.3.2"
SKILL_DIR = "hermes/alucolux-quote"


def _read_env_file() -> Dict[str, str]:
    out: Dict[str, str] = {}
    env_file = app_root() / ".env.api"
    if not env_file.is_file():
        return out
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def read_bot_api_key() -> str:
    env = _read_env_file()
    if env.get("ALUCOLUX_BOT_API_KEY"):
        return env["ALUCOLUX_BOT_API_KEY"]
    return os.environ.get("ALUCOLUX_BOT_API_KEY", "").strip()


def _skill_source_dir() -> Path:
    root = app_root()
    candidate = root / SKILL_DIR
    if candidate.is_dir():
        return candidate
    alt = bundle_root() / SKILL_DIR
    if alt.is_dir():
        return alt
    raise FileNotFoundError(f"Skill 目录不存在: {SKILL_DIR}")


def _read_skill_file(name: str) -> str:
    path = _skill_source_dir() / name
    if not path.is_file():
        raise FileNotFoundError(str(path))
    return path.read_text(encoding="utf-8")


def _build_agent_setup_md(*, api_base: str, generated_at: str) -> str:
    return f"""# ALUCOLUX Bot Agent 自动配置说明

> 生成时间：{generated_at}  
> **Bot 模式**：使用 Bot API Key，无需 ALUCOLUX 用户名与企微 userid 映射。  
> 权限与话术由 **Skill** 管控；API 返回 `public`（对用户）与 `internal`（内部，Skill 决定是否展示）。

## 第一步：阅读清单

1. `manifest.json` — 版本与 API 地址
2. `config/config.env` — **Bot API Key（敏感）**
3. `skill/SKILL.md` — 对话与保密规则

## 第二步：安装 Skill

| 源文件 | 目标 |
|--------|------|
| `skill/SKILL.md` | `<skills>/alucolux-quote/SKILL.md` |
| `skill/reference.md` | `<skills>/alucolux-quote/reference.md` |

## 第三步：注入环境变量

从 `config/config.env` 设置：

```
ALUCOLUX_API_BASE={api_base}
ALUCOLUX_BOT_API_KEY=<见 config.env>
```

或使用 `config/hermes.env.json` 批量导入。

**不要**设置 `X-ALUCOLUX-Username`；Bot Key  alone 即可调用 API。

## 第四步：验证

```bash
bash verify/test_api.sh
```

或 PowerShell：`.\\verify\\test_api.ps1`

期望：`mode` 为 `bot`，且响应含 `public` 与 `internal` 字段。

## 第五步：Skill 保密规则（必遵）

- 日常报价：**只**用 `public` 回复；**禁止主动**问用户要不要查成本/内部复核
- `internal` 含保本价等 — **禁止主动展示、禁止主动 Offer**
- 仅当**用户先提出**内部复核且完成「确认复核」后，才可引用 `internal`
- 谁能在 Bot 里触发内部复核 — 由 **Hermes/企微 Bot 平台** 配置，非 ALUCOLUX 映射

## 第六步：向管理员确认

1. Skill 安装路径
2. API health 通过
3. 测试报价成功（用户侧只见销售三价）

## 在线文档

- Swagger：`{api_base}/api/docs`
- Health：`{api_base}/api/health`
"""


def _build_manifest(*, api_base: str, app_version: str, generated_at: str) -> Dict[str, Any]:
    return {
        "bundle_version": BUNDLE_VERSION,
        "app_version": app_version,
        "generated_at": generated_at,
        "auth_mode": "bot",
        "skill_name": "alucolux-quote",
        "api_base": api_base.rstrip("/"),
        "endpoints": {
            "health": "/api/health",
            "quote": "/api/v1/quote",
            "compare": "/api/v1/quote/compare",
            "colors": "/api/v1/colors",
            "docs": "/api/docs",
        },
        "setup_readme": "AGENT_SETUP.md",
    }


def _build_config_env(api_base: str, bot_api_key: str) -> str:
    lines = [
        "# ALUCOLUX Bot Agent — 含敏感 Bot API Key",
        f"ALUCOLUX_API_BASE={api_base.rstrip('/')}",
        f"ALUCOLUX_BOT_API_KEY={bot_api_key}",
    ]
    return "\n".join(lines) + "\n"


def _build_test_sh(api_base: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source config/config.env
BASE="${{ALUCOLUX_API_BASE:-{api_base}}}"
echo "==> Health"
curl -sf "$BASE/api/health"
echo
echo "==> Quote (bot mode)"
curl -sf -X POST "$BASE/api/v1/quote" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: $ALUCOLUX_BOT_API_KEY" \\
  -d '{{"contract_area":1000,"width_m":1.5,"length_m":3.0,"thickness_mm":3.0,"coating_type":"PVDF2"}}'
echo
echo "==> OK"
"""


def _build_test_ps1(api_base: str) -> str:
    return f"""# ALUCOLUX Bot API 连通性测试
$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $MyInvocation.MyCommand.Path -Parent) -Parent
Get-Content (Join-Path $root "config\\config.env") | ForEach-Object {{
    if ($_ -match '^([^#=]+)=(.*)$') {{ Set-Item -Path "env:$($matches[1].Trim())" -Value $matches[2].Trim() }}
}}
$base = if ($env:ALUCOLUX_API_BASE) {{ $env:ALUCOLUX_API_BASE }} else {{ "{api_base}" }}
Write-Host "==> Health"
(Invoke-WebRequest -Uri "$base/api/health" -UseBasicParsing).Content
Write-Host "==> Quote (bot)"
$body = '{{"contract_area":1000,"width_m":1.5,"length_m":3.0,"thickness_mm":3.0,"coating_type":"PVDF2"}}'
$headers = @{{ "X-API-Key" = $env:ALUCOLUX_BOT_API_KEY }}
(Invoke-WebRequest -Uri "$base/api/v1/quote" -Method POST -Body $body -ContentType "application/json" -Headers $headers -UseBasicParsing).Content
Write-Host "==> OK"
"""


def build_agent_bundle_zip(
    *,
    api_base: str,
    bot_api_key: str,
    app_version: str,
) -> bytes:
    if not bot_api_key:
        raise ValueError("bot_api_key_missing")
    api_base = api_base.strip().rstrip("/") or DEFAULT_API_BASE
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        def add_text(name: str, content: str) -> None:
            zf.writestr(name, content)

        add_text("AGENT_SETUP.md", _build_agent_setup_md(api_base=api_base, generated_at=generated_at))
        add_text(
            "manifest.json",
            json.dumps(
                _build_manifest(api_base=api_base, app_version=app_version, generated_at=generated_at),
                ensure_ascii=False,
                indent=2,
            ) + "\n",
        )
        add_text("skill/SKILL.md", _read_skill_file("SKILL.md"))
        add_text("skill/reference.md", _read_skill_file("reference.md"))
        add_text("config/config.env", _build_config_env(api_base, bot_api_key))
        add_text(
            "config/hermes.env.json",
            json.dumps(
                {"ALUCOLUX_API_BASE": api_base, "ALUCOLUX_BOT_API_KEY": bot_api_key},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
        )
        add_text("verify/test_api.sh", _build_test_sh(api_base))
        add_text("verify/test_api.ps1", _build_test_ps1(api_base))

    return buf.getvalue()


def bundle_filename(app_version: str) -> str:
    ts = datetime.now().strftime("%Y%m%d")
    return f"ALUCOLUX-bot-agent_{app_version}_{ts}.zip"
