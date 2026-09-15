import argparse, sys

def build_parser():
    p = argparse.ArgumentParser(prog="tool")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--yolo", action="store_true")
    run.add_argument("path")
    gw = sub.add_parser("gateway")
    gsub = gw.add_subparsers(dest="gcmd", required=True)
    gw_run = gsub.add_parser("run")
    gw_run.add_argument("port", type=int)
    return p

def main(argv=None):
    ns = build_parser().parse_args(argv)
    if ns.cmd == "run":
        return f"run {ns.path} yolo={ns.yolo}"
    if ns.cmd == "gateway":
        return f"gateway run port={ns.port} yolo={getattr(ns,'yolo',False)}"

if __name__ == "__main__":
    print(main())
