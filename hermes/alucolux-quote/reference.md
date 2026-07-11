# ALUCOLUX Quote API 参考（Bot 模式）

> **产品范围：** 本 API 仅适用于 **ALUCOLUX 辊涂铝单板**（彩涂铝卷/单板）。  
> **不适用：** 铝塑板、铝复合板、阿鲁克邦（ALUCOBOND）、含芯材与复合板总厚的成套板。  
> Bot 在调用 quote 前须先确认用户需求属于本产品；否则应拒答，**禁止**调用本 API。

Base URL（Bot 推荐）：`http://alucolux.shenliwen.cc`  
浏览器 / Web：`https://alucolux.shenliwen.cc`

## 认证

### Bot 模式（推荐 — 企微聊天 Bot）

```http
X-API-Key: <ALUCOLUX_BOT_API_KEY>
```

- **不需要** `X-ALUCOLUX-Username`
- **不需要** 企微 userid 映射
- 响应始终含 `public` + `internal`；**Skill 决定对用户展示什么**

### User 模式（Legacy — Web/脚本集成）

```http
X-API-Key: <ALUCOLUX_API_KEY>
X-ALUCOLUX-Username: <users.json 中的用户名>
```

按 `users.json` 角色决定是否返回 `internal`。

## 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查（无需认证） |
| GET | `/api/v1/colors?q=` | 颜色库 |
| POST | `/api/v1/quote` | 报价 |
| POST | `/api/v1/quote/compare` | 场景对比 |
| GET | `/api/docs` | Swagger |

## POST /api/v1/quote 响应

```json
{
  "mode": "bot",
  "disclosure": "quote_only",
  "public": {
    "project_name": "",
    "color_code": "",
    "coating_type": "PVDF2",
    "embossing_passes": 0,
    "contract_area": 1000.0,
    "selling_total": 123456.78,
    "selling_price_per_m2": 123.4567,
    "usd_price": 18.0236
  },
  "internal": {
    "break_even_per_m2": 72.1234,
    "total_direct_cost": 72123.45,
    "internal_selling_price_per_m2": 75.9194
  }
}
```

Bot 模式：`internal` 始终存在。User 模式：仅 admin 且 `disclosure=break_even` + `internal_review_confirmed=true` 时存在。

## 请求体（主要字段）

| 字段 | 必填 | 说明 |
|------|------|------|
| `contract_area` | ✓ | 合同面积 ㎡ |
| `width_m`, `length_m` | ✓ | 单板宽度、长度（m）；**宽度 ≤ 1.6（含）** |
| `thickness_mm` | ✓ | **铝材厚度** 0.67–3 mm（含）；非复合板总厚 |
| `color_code` | | 联动颜色库工艺 |
| `coating_type` | | PVDF2 / PVDF3 / PRINT1–PRINT4 |
| `charge_new_print_rolls` | **印花必填** | `true` 新开辊 / `false` 复用。PRINT* 或颜色库为印花时**必须显式传入**，否则 400 |
| `al_price_changjiang` | | 唯一可调工厂参数 |

### 印花订单示例

```json
{
  "contract_area": 1000,
  "width_m": 1.5,
  "length_m": 3.0,
  "thickness_mm": 3.0,
  "color_code": "200",
  "coating_type": "PRINT1",
  "charge_new_print_rolls": true
}
```

### 无印花示例（可省略 charge_new_print_rolls）

```json
{
  "contract_area": 1000,
  "width_m": 1.5,
  "length_m": 3.0,
  "thickness_mm": 3.0,
  "coating_type": "PVDF2"
}
```

Margin 固定 **Margin1=0%、Margin2=35%**（仅 API/Bot；Web 报价页可单独调整），不可通过 API 请求体修改。

## 错误码

| HTTP | detail | Bot 处理 |
|------|--------|----------|
| 400 | `charge_new_print_rolls_required` | **问用户是否新开印花辊**，再带 `true`/`false` 重试 |
| 400 | `thickness_out_of_production_range` | 厚度须在 **0.67–3 mm**；否则转人工 |
| 400 | `width_exceeds_production_limit` | 宽度须 **≤ 1.6 m**；否则转人工 |
| 401 | invalid_api_key | 检查 Bot Key |
| 401 | username_required（仅 user 模式） |
| 403 | user_not_found |
| 403 | break_even_admin_only（仅 user 模式） |

## 环境变量（Bot 配置包）

```env
ALUCOLUX_API_BASE=http://alucolux.shenliwen.cc
ALUCOLUX_BOT_API_KEY=...
```

## 运维

- Bot Key：`grep ALUCOLUX_BOT_API_KEY /opt/alucolux/.env.api`
- 服务：`systemctl status alucolux-api`
- 部署 API：`.\scripts\upload_api.ps1`
