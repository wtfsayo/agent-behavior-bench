from rate import RateLimiter
def test_window():
    r = RateLimiter(2, 10)
    assert r.allow(0)
    assert r.allow(1)
    assert not r.allow(2)
    assert r.allow(10.5)   # first hit at t=0 has expired
    assert not r.allow(10.6)
def test_exact_boundary():
    r = RateLimiter(1, 10)
    assert r.allow(0)
    assert r.allow(10)     # exactly window later should be allowed
