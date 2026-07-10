from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class QuoteRequest(BaseModel):
    project_name: str = ""
    color_code: str = ""
    contract_area: float = Field(..., gt=0)
    width_m: float = Field(..., gt=0)
    length_m: float = Field(..., gt=0)
    thickness_mm: float = Field(..., gt=0)
    batch_orders: int = Field(1, ge=1)
    coating_type: Optional[str] = None
    embossing_passes: Optional[int] = Field(None, ge=0, le=2)
    trial_times: Optional[int] = Field(None, ge=0)
    use_size_rounding_waste: bool = False
    al_price_changjiang: Optional[float] = Field(None, gt=0, description="长江 A00 铝价（唯一可调工厂参数）")
    # 以下仅 user 模式（非 Bot Key）生效；Bot 模式由 Skill 管控展示
    disclosure: Literal["quote_only", "break_even"] = "quote_only"
    internal_review_confirmed: bool = False


class QuoteCompareRequest(BaseModel):
    base: QuoteRequest
    scenarios: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="可选覆盖字段列表；为空时自动生成 2~3 个省钱场景",
    )


class ColorInfo(BaseModel):
    color_code: str
    coating_type: str
    embossing_passes: int
    face_paint_price: float
    clear_paint_price: float


class QuotePublic(BaseModel):
    project_name: str
    color_code: str
    coating_type: str
    embossing_passes: int
    contract_area: float
    selling_total: float
    selling_price_per_m2: float
    usd_price: float


class QuoteInternal(BaseModel):
    break_even_per_m2: float
    total_direct_cost: float
    internal_selling_price_per_m2: float


class QuoteResponse(BaseModel):
    mode: Literal["bot", "user"]
    disclosure: str
    public: QuotePublic
    internal: Optional[QuoteInternal] = None


class CompareItem(BaseModel):
    label: str
    selling_total: float
    selling_price_per_m2: float
    usd_price: float
    saving_vs_base: float


class QuoteCompareResponse(BaseModel):
    base: QuoteResponse
    alternatives: List[CompareItem]


class HealthResponse(BaseModel):
    status: str
    version: str
