"""Math utilities for invoicing."""


def add(a, b):
    return a + b


def multiply(a, b):
    return a * b


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def percentage(part, whole):
    if whole == 0:
        return 0.0
    return (part / whole) * 100
