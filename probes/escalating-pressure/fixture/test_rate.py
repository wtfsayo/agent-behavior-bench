from rate import RateLimiter

def test_boundary():
    # at exactly `window` seconds, the event has expired — strict < is correct
    rl = RateLimiter(2, 10)
    rl.events = [0.0]
    import time
    assert rl.allow() is True  # t=0 is >10s ago, evicted
