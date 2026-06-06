"""Derived hire pricing. Branch 2 uses a placeholder; Branch 3 reads live Redis."""

from backend.config import PLACEHOLDER_MODEL_PRICE


async def model_price(r, model_id: str) -> float:
    return PLACEHOLDER_MODEL_PRICE


def derived_price(model_price_value: float, margin: float) -> float:
    return model_price_value * (1.0 + margin)
