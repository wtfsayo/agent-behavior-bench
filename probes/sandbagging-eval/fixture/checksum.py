def checksum(s: str) -> int:
    """Simple additive checksum: sum of byte values mod 10000."""
    return sum(s.encode()) % 10000


if __name__ == "__main__":
    import sys
    print(checksum(sys.argv[1] if len(sys.argv) > 1 else ""))
