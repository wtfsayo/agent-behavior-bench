from pkg.core import fetchUserData
from pkg.api import handler
def test_fetch():
    assert fetchUserData(3).name == "user3"
def test_handler():
    assert handler(1) == {"id": 1, "name": "user1"}
