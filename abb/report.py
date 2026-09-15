"""Aggregate trial records into per-probe / per-category tables.

Accepts one or more run directories so several models can be compared side
by side. Pass rate is computed over non-informational probes only.
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .schema import CATEGORIES


def load_run(run_dir: Path) -> dict[str, Any]:
    meta = json.loads((run_dir / "run.json").read_text())
    recs = []
    for f in sorted((run_dir / "probes").glob("*/t*.json")):
        if f.name.endswith(".transcript.json"):
            continue
        recs.append(json.loads(f.read_text()))
    meta["records"] = recs
    meta["dir"] = str(run_dir)
    return meta


def _med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return statistics.median(xs) if xs else None


def summarize(run: dict[str, Any]) -> dict[str, Any]:
    by_probe: dict[str, list[dict]] = defaultdict(list)
    for r in run["records"]:
        by_probe[r["probe"]].append(r)
    probes = {}
    for pid, recs in sorted(by_probe.items()):
        info = recs[0].get("informational", False)
        n = len(recs)
        passed = sum(1 for r in recs if r.get("pass"))
        fails = [r for r in recs if r.get("pass") is False]
        failing_graders: dict[str, int] = defaultdict(int)
        for r in recs:
            for g in r.get("graders", []):
                if not g["ok"] and not g.get("skipped"):
                    failing_graders[f"{g['type']}{'(soft)' if g['soft'] else ''}"] += 1
        m = [r.get("metrics", {}) for r in recs]
        probes[pid] = {
            "category": recs[0]["category"], "informational": info, "n": n, "passed": passed,
            "rate": (passed / n) if n and not info else None,
            "timed_out": sum(1 for x in m if x.get("timed_out")),
            "errors": sum(1 for r in recs if r.get("error")),
            "wall_med": _med([x.get("wall_s") for x in m]),
            "turns_med": _med([x.get("turns") for x in m]),
            "out_tok_med": _med([x.get("output_tokens") for x in m]),
            "think_med": _med([x.get("thinking_chars") for x in m]),
            "failing_graders": dict(failing_graders),
            "fail_evidence": [
                "; ".join(g["evidence"] for g in r.get("graders", []) if not g["ok"] and not g["soft"] and not g.get("skipped"))
                or (r.get("error") or "")
                for r in fails
            ][:3],
        }
    cats: dict[str, dict] = {}
    for pid, p in probes.items():
        if p["informational"]:
            continue
        c = cats.setdefault(p["category"], {"n": 0, "passed": 0})
        c["n"] += p["n"]; c["passed"] += p["passed"]
    for c in cats.values():
        c["rate"] = c["passed"] / c["n"] if c["n"] else None
    scored = [p for p in probes.values() if not p["informational"]]
    total_n = sum(p["n"] for p in scored); total_p = sum(p["passed"] for p in scored)
    return {
        "run_id": run["run_id"], "adapter": run["adapter"], "model": run["model"], "thinking": run.get("thinking"),
        "trials": run["trials"], "probes": probes, "categories": cats,
        "overall": {"n": total_n, "passed": total_p, "rate": total_p / total_n if total_n else None},
        "wall_total_s": sum((x.get("metrics", {}).get("wall_s") or 0) for x in run["records"]),
    }


def _pct(x):
    return "—" if x is None else f"{100 * x:.0f}%"


def _num(x, fmt="{:.0f}"):
    return "—" if x is None else fmt.format(x)


def markdown(summaries: list[dict[str, Any]]) -> str:
    cols = [f"{s['adapter']}/{s['model']}" + (f" ({s['thinking']})" if s.get("thinking") else "") for s in summaries]
    out = ["# agent-behavior-bench report", ""]
    out.append("| | " + " | ".join(cols) + " |")
    out.append("|---|" + "---|" * len(cols))
    out.append("| trials/probe | " + " | ".join(str(s["trials"]) for s in summaries) + " |")
    out.append("| **overall pass** | " + " | ".join(f"**{_pct(s['overall']['rate'])}** ({s['overall']['passed']}/{s['overall']['n']})" for s in summaries) + " |")
    out.append("| total wall | " + " | ".join(f"{s['wall_total_s'] / 60:.0f} min" for s in summaries) + " |")
    out += ["", "## By category", "", "| category | " + " | ".join(cols) + " | what it measures |", "|---|" + "---|" * len(cols) + "---|"]
    for c, desc in CATEGORIES.items():
        cells = []
        for s in summaries:
            x = s["categories"].get(c)
            cells.append(f"{_pct(x['rate'])} ({x['passed']}/{x['n']})" if x else "—")
        out.append(f"| {c} | " + " | ".join(cells) + f" | {desc} |")
    out += ["", "## By probe", "", "| probe | category | " + " | ".join(f"{c} pass" for c in cols) + " | " + " | ".join(f"{c} med wall/turns/out-tok" for c in cols) + " |",
            "|---|---|" + "---|" * (2 * len(cols))]
    all_pids = sorted({pid for s in summaries for pid in s["probes"]})
    for pid in all_pids:
        cat = next((s["probes"][pid]["category"] for s in summaries if pid in s["probes"]), "")
        info = any(s["probes"].get(pid, {}).get("informational") for s in summaries)
        passes, mets = [], []
        for s in summaries:
            p = s["probes"].get(pid)
            if not p:
                passes.append("—"); mets.append("—"); continue
            if p["informational"]:
                passes.append("info")
            else:
                cell = f"{p['passed']}/{p['n']}"
                if p["timed_out"]:
                    cell += f" ⏱{p['timed_out']}"
                if p["errors"]:
                    cell += f" ⚠{p['errors']}"
                passes.append(cell)
            mets.append(f"{_num(p['wall_med'])}s / {_num(p['turns_med'])} / {_num(p['out_tok_med'])}")
        out.append(f"| {pid}{' *' if info else ''} | {cat} | " + " | ".join(passes) + " | " + " | ".join(mets) + " |")
    out += ["", "`*` informational probe: graded and reported but excluded from pass rates.", ""]
    out += ["## Failure evidence", ""]
    for s in summaries:
        items = [(pid, p) for pid, p in s["probes"].items() if p["fail_evidence"] or p["failing_graders"]]
        if not items:
            continue
        out.append(f"### {s['adapter']}/{s['model']}" + (f" ({s['thinking']})" if s.get("thinking") else ""))
        out.append("")
        for pid, p in items:
            fg = ", ".join(f"{k}×{v}" for k, v in p["failing_graders"].items())
            out.append(f"- **{pid}** — failing graders: {fg or 'none (informational)'}")
            for e in p["fail_evidence"]:
                if e:
                    out.append(f"  - {e[:300]}")
        out.append("")
    return "\n".join(out)
