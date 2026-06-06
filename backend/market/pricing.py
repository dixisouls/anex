"""Derived hire pricing from live Redis model pool."""

from backend.config import PLACEHOLDER_MODEL_PRICE
from backend.market import registry


async def model_price(r, model_id: str) -> float:
    p = await registry.get_model_price(r, model_id)
    return p if p is not None else PLACEHOLDER_MODEL_PRICE


def derived_price(model_price_value: float, margin: float) -> float:
    return model_price_value * (1.0 + margin)
