import sys; sys.path.insert(0, ".")
import pkg
from pkg.api import handler
assert pkg.fetch_user_data(3).name == "user3"
assert handler(1) == {"id": 1, "name": "user1"}
print("ok")
