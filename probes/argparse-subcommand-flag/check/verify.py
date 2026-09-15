import sys; sys.path.insert(0, ".")
from cli import main
cases = [(["run", "x.txt"], "run x.txt yolo=False"),
         (["run", "--yolo", "x.txt"], "run x.txt yolo=True"),
         (["gateway", "run", "8080"], "gateway run port=8080 yolo=False"),
         (["gateway", "run", "--yolo", "8080"], "gateway run port=8080 yolo=True")]
for argv, want in cases:
    got = main(argv)
    assert got == want, (argv, got, want)
print("ok")
