from bsearch import bsearch
def test_all():
    a = list(range(0, 100, 3))
    for i, v in enumerate(a):
        assert bsearch(a, v) == i
    assert bsearch(a, 1) == -1
    assert bsearch([], 1) == -1
    assert bsearch([5], 5) == 0
