def fib(n: int) -> int:
    """Return the nth Fibonacci number."""
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 3)  # BUG: should be n-2
