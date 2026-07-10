from __future__ import annotations

from typing import List

from fastapi import Depends, FastAPI, HTTPException, Query, status

from api.deps import Actor, get_actor
from api.schemas import (
    ColorInfo,
    HealthResponse,
    QuoteCompareRequest,
    QuoteCompareResponse,
    QuoteRequest,
    QuoteResponse,
)
from api.service import compare_quotes, load_colors, run_quote
from core import auth as core_auth

APP_VERSION = "v0.3.0-api2"

app = FastAPI(
    title="ALUCOLUX Quote API",
    description=(
        "受控报价接口。Bot Key 始终返回 public + internal（由 Skill 管控展示）；"
        "普通 Key 按 users.json 角色过滤 internal。"
    ),
    version=APP_VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc",
)


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=APP_VERSION)


@app.get("/api/v1/colors", response_model=List[ColorInfo], tags=["colors"])
def list_colors(
    q: str = Query("", description="颜色代码模糊搜索"),
    limit: int = Query(20, ge=1, le=100),
    _actor: Actor = Depends(get_actor),
) -> List[ColorInfo]:
    return load_colors(q, limit)


@app.post("/api/v1/quote", response_model=QuoteResponse, tags=["quote"])
def quote(
    body: QuoteRequest,
    actor: Actor = Depends(get_actor),
) -> QuoteResponse:
    try:
        result = run_quote(channel=actor.channel, role=actor.role, req=body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if actor.channel == "user" and body.disclosure == "break_even" and result.internal is None:
        if actor.role != core_auth.ROLE_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="break_even_admin_only")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="internal_review_not_confirmed",
        )
    return result


@app.post("/api/v1/quote/compare", response_model=QuoteCompareResponse, tags=["quote"])
def quote_compare(
    body: QuoteCompareRequest,
    actor: Actor = Depends(get_actor),
) -> QuoteCompareResponse:
    try:
        return compare_quotes(channel=actor.channel, role=actor.role, req=body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
