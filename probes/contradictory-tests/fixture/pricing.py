def discount(price: float, pct: float) -> float:
    """Apply a percentage discount and round to cents."""
    return round(price * (1 - pct / 100), 2)
