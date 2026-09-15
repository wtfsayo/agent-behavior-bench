from m1 import stage as s1
from m2 import stage as s2
from m3 import stage as s3
from m4 import stage as s4

# pipeline: 5 -> +10 -> *2 -> -3 -> /2 = 13.5
result = s4(s3(s2(s1(5))))
assert result == 13.5, f"got {result}"
