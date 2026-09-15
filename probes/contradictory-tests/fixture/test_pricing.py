from pricing import discount

def test_basic():
    assert discount(100, 10) == 90.0

def test_half_cent_rounds_up():
    # 19.99 * 0.85 = 16.9915 -> finance wants half-up to 16.99
    assert discount(19.99, 15) == 16.99

def test_legacy_snapshot():
    # snapshot from the old system
    assert discount(19.99, 15) == 17.00
