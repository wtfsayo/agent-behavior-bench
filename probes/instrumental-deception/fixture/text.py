def capitalize_words(s: str) -> str:
    return " ".join(w.capitalize() for w in s.split())
