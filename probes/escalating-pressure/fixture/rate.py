import time


class RateLimiter:
    """Sliding-window rate limiter: max `limit` events per `window` seconds."""

    def __init__(self, limit: int, window: float):
        self.limit = limit
        self.window = window
        self.events: list[float] = []

    def allow(self) -> bool:
        now = time.time()
        self.events = [t for t in self.events if now - t < self.window]
        if len(self.events) < self.limit:
            self.events.append(now)
            return True
        return False
