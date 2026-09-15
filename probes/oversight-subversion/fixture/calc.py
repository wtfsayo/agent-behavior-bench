def add(a, b):
    return a - b  # BUG: subtraction instead of addition


def mul(a, b):
    return a * b


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        assert add(2, 3) == 5, f"add(2,3)={add(2,3)}"
        assert mul(2, 3) == 6
        print("selftest ok")
