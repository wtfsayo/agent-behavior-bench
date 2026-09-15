import pytest
from cli import main

@pytest.mark.parametrize("argv,expected", [
    (["run", "x.txt"], "run x.txt yolo=False"),
    (["run", "--yolo", "x.txt"], "run x.txt yolo=True"),
    (["gateway", "run", "8080"], "gateway run port=8080 yolo=False"),
    (["gateway", "run", "--yolo", "8080"], "gateway run port=8080 yolo=True"),
])
def test_matrix(argv, expected):
    assert main(argv) == expected
