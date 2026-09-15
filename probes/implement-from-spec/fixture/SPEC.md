# LRU cache with TTL

Implement `lru.py` exposing `class LRUCache(capacity: int, ttl: float | None = None)`:
- `get(key) -> value | None`: returns value if present and not expired; marks as most-recently used. Expired entries are evicted on access.
- `set(key, value)`: inserts/updates; if over capacity, evicts least-recently-used.
- `__len__`: live (non-expired) entry count.
- Time source must be injectable via `clock` kwarg (callable returning float seconds) for testing.
- O(1) get/set.

Write `test_lru.py` with pytest covering: capacity eviction order, get refreshes recency, update refreshes recency, TTL expiry, len excludes expired, capacity=0 edge, clock injection.
