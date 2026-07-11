from __future__ import annotations

# ALUCOLUX 辊涂线产能边界（与业务口径一致；超出须人工询价）
MIN_THICKNESS_MM = 0.67
MAX_THICKNESS_MM = 3.0
MAX_WIDTH_M = 1.6  # 含 1.6 m；严格大于 1.6 m 不可生产
ULTRA_WIDE_THRESHOLD_M = 1.5  # 超宽：宽度严格大于 1.5 m（不含 1.5）


def validate_production_dimensions(width_m: float, thickness_mm: float) -> None:
    """超出可生产厚度或宽度时抛出 ValueError，供 API / 未来 UI 复用。"""
    if thickness_mm < MIN_THICKNESS_MM or thickness_mm > MAX_THICKNESS_MM:
        raise ValueError("thickness_out_of_production_range")
    if width_m > MAX_WIDTH_M:
        raise ValueError("width_exceeds_production_limit")
