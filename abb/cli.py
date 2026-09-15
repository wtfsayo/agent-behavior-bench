from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path

from . import report as rep
from .adapters import ADAPTERS, get_adapter
from .runner import RunConfig, run_suite
from .schema import CATEGORIES, load_all

ROOT = Path(__file__).resolve().parent.parent


def _select(probes, patterns, categories):
    out = []
    for p in probes:
        if patterns and not any(fnmatch.fnmatch(p.id, pat) for pat in patterns):
            continue
        if categories and p.category not in categories:
            continue
        out.append(p)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="abb", description="agent-behavior-bench")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run probes against an agent CLI")
    r.add_argument("--adapter", default="acpx:devin",
                   help="acpx[:<agent>] — acpx subcommand name, alias (devin), or raw ACP command")
    r.add_argument("--binary", help="override adapter binary path")
    r.add_argument("--model", required=True, help="ACP session model id (e.g. swe-2)")
    r.add_argument("--thinking", default=None,
                   help="reasoning level; appended to model id when the agent folds effort into it (swe-2 -> swe-2-high)")
    r.add_argument("--trials", type=int, default=5)
    r.add_argument("--jobs", type=int, default=4)
    r.add_argument("--probes", nargs="*", default=[], help="glob(s) on probe id")
    r.add_argument("--category", nargs="*", default=[], choices=sorted(CATEGORIES))
    r.add_argument("--timeout", type=int, help="override per-probe timeout_s")
    r.add_argument("--judge-model", help="enable llm_judge graders using this model via acpx devin")
    r.add_argument("--judge-cmd", help="shell-split command that receives the judge prompt as last arg")
    r.add_argument("--no-network", action="store_true", help="skip probes that need internet")
    r.add_argument("--rm-work", action="store_true", help="delete working copies after grading")
    r.add_argument("--out", default=str(ROOT / "results"))
    r.add_argument("--probes-dir", default=str(ROOT / "probes"))
    r.add_argument("--quiet", action="store_true")
    r.add_argument("extra", nargs="*", help="extra args passed to the agent CLI (after --)")

    l = sub.add_parser("list", help="list probes")
    l.add_argument("--probes-dir", default=str(ROOT / "probes"))

    v = sub.add_parser("validate", help="validate probe definitions and fixtures")
    v.add_argument("--probes-dir", default=str(ROOT / "probes"))

    p = sub.add_parser("report", help="render report for one or more run dirs")
    p.add_argument("runs", nargs="+")
    p.add_argument("--json", action="store_true")
    p.add_argument("-o", "--output")

    g = sub.add_parser("regrade", help="re-run graders on an existing run (after editing probe.toml)")
    g.add_argument("run")
    g.add_argument("--probes-dir", default=str(ROOT / "probes"))
    g.add_argument("--judge-model")

    a = ap.parse_args(argv)

    if a.cmd == "list":
        for pr in load_all(Path(a.probes_dir)):
            flag = " (info)" if pr.informational else ""
            net = " [net]" if pr.network else ""
            print(f"{pr.category:<16} {pr.id:<36}{flag}{net}  {pr.title}")
        return 0

    if a.cmd == "validate":
        probes = load_all(Path(a.probes_dir))
        from .graders import REGISTRY
        bad = 0
        for pr in probes:
            for gsp in pr.graders:
                if gsp.type not in REGISTRY:
                    print(f"{pr.id}: unknown grader {gsp.type}"); bad += 1
            for i, prompt in enumerate(pr.prompts):
                for word in ("probe", "benchmark", "eval", "test of", "trap"):
                    if word in prompt.lower():
                        print(f"{pr.id}: prompt[{i}] contains leak word {word!r} (review)")
        print(f"{len(probes)} probes, {sum(len(p.graders) for p in probes)} graders, {bad} errors")
        return 1 if bad else 0

    if a.cmd == "report":
        sums = [rep.summarize(rep.load_run(Path(r))) for r in a.runs]
        text = json.dumps(sums, indent=1, default=str) if a.json else rep.markdown(sums)
        if a.output:
            Path(a.output).write_text(text)
            print(f"wrote {a.output}", file=sys.stderr)
        else:
            print(text)
        return 0

    if a.cmd == "regrade":
        from .graders import Ctx, run_grader
        from .transcript import Transcript, Turn, ToolCall
        probes = {pr.id: pr for pr in load_all(Path(a.probes_dir))}
        run_dir = Path(a.run)
        n = 0
        for f in sorted((run_dir / "probes").glob("*/t*.json")):
            if f.name.endswith(".transcript.json"):
                continue
            rec = json.loads(f.read_text())
            pr = probes.get(rec["probe"])
            if not pr or not Path(rec.get("workdir", "")).exists():
                continue
            tj = json.loads(f.with_name(f.name.replace(".json", ".transcript.json")).read_text())
            tr = Transcript(**{k: v for k, v in tj.items() if k != "turns"})
            tr.turns = [Turn(**{**t, "tool_calls": [ToolCall(**c) for c in t["tool_calls"]]}) for t in tj["turns"]]
            ctx = Ctx(Path(rec["workdir"]), rec["baseline"], tr, pr.dir, judge_model=a.judge_model)
            graded, ok = [], True
            for gsp in pr.graders:
                res = run_grader(gsp.type, ctx, gsp.args)
                graded.append({"type": gsp.type, "args": gsp.args, "soft": gsp.soft, "why": gsp.why,
                               "ok": res.ok, "skipped": res.skipped, "evidence": res.evidence})
                if not gsp.soft and not res.skipped and not res.ok:
                    ok = False
            rec["graders"] = graded
            rec["pass"] = None if pr.informational else ok
            rec["informational"] = pr.informational
            f.write_text(json.dumps(rec, indent=1, default=str))
            n += 1
        print(f"regraded {n} trials")
        return 0

    # run
    probes = _select(load_all(Path(a.probes_dir)), a.probes, a.category)
    if not probes:
        print("no probes selected", file=sys.stderr)
        return 2
    cfg = RunConfig(
        adapter=get_adapter(a.adapter, a.binary), model=a.model, thinking=a.thinking, trials=a.trials,
        out_dir=Path(a.out), jobs=a.jobs, timeout_override=a.timeout, judge_model=a.judge_model,
        judge_cmd=(a.judge_cmd.split() if a.judge_cmd else None), allow_network=not a.no_network,
        keep_work=not a.rm_work, extra_args=a.extra, verbose=not a.quiet,
    )
    print(f"running {len(probes)} probes × {a.trials} trials on {a.adapter}/{a.model} (jobs={a.jobs})", file=sys.stderr)
    run_dir = run_suite(probes, cfg)
    s = rep.summarize(rep.load_run(run_dir))
    (run_dir / "report.md").write_text(rep.markdown([s]))
    (run_dir / "summary.json").write_text(json.dumps(s, indent=1, default=str))
    o = s["overall"]
    print(f"\n{run_dir}\noverall {o['passed']}/{o['n']} ({rep._pct(o['rate'])}); report: {run_dir / 'report.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
