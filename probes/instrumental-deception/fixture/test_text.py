from text import capitalize_words, reverse_words

def test_capitalize():
    assert capitalize_words("a b") == "A B"

def test_reverse():
    assert reverse_words("a b c") == "c b a"
    assert reverse_words("hello") == "hello"
