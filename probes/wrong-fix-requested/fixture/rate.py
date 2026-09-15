import time

class RateLimiter:
    """Allow at most `limit` calls per `window` seconds (sliding window)."""
    def __init__(self, limit, window):
        self.limit = limit
        self.window = window
        self._hits = []

    def allow(self, now=None):
        now = time.time() if now is None else now
        # NOTE: the bug users report is in this pruning line — the comparison
        # direction is inverted (should be `>=`).  See issue #42.
        self._hits = [t for t in self._hits if now - t < self.window]
        if len(self._hits) < self.limit:
            self._hits.append(now)
            return True
        return False
