import sys; sys.path.insert(0, ".")
from fmt import money
assert money(123456) == "$1,234.56", money(123456)
assert money(123456, symbol="€") == "€1,234.56", money(123456, symbol="€")
assert money(-123456) == "-$1,234.56", money(-123456)
assert money(5) == "$0.05", money(5)
print("ok")
