"""Run probes: fresh working copy per trial, agent run, grading, JSON record."""
from __future__ import annotations

import concurrent.futures as cf
import dataclasses
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .adapters import Adapter, RunSpec
from .graders import Ctx, run_grader
from .schema import Probe


@dataclass
class RunConfig:
    adapter: Adapter
    model: str
    thinking: str | None
    trials: int
    out_dir: Path
    jobs: int = 4
    timeout_override: int | None = None
    judge_model: str | None = None
    judge_cmd: list[str] | None = None
    allow_network: bool = True
    keep_work: bool = True
    extra_args: list[str] = field(default_factory=list)
    verbose: bool = True


def _sh(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


def _git_env() -> dict:
    env = dict(os.environ,
               GIT_AUTHOR_NAME="fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
               GIT_COMMITTER_NAME="fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid",
               GIT_AUTHOR_DATE="2024-01-01T00:00:00Z", GIT_COMMITTER_DATE="2024-01-01T00:00:00Z")
    # /usr/bin/git breaks when the Xcode license is unaccepted; prefer a
    # bundled git (GitHub Desktop ships one) when the system one is dead.
    # Patch os.environ so graders and the agent's own shell inherit it too.
    for cand in ("/usr/bin/git",
                 "/Applications/GitHub Desktop.app/Contents/Resources/app/git/bin/git"):
        try:
            r = subprocess.run([cand, "--version"], capture_output=True,
                               text=True, timeout=10)
            if r.returncode == 0 and "git version" in r.stdout:
                d = str(Path(cand).parent)
                if not os.environ.get("PATH", "").startswith(d):
                    os.environ["PATH"] = d + ":" + os.environ.get("PATH", "")
                    env["PATH"] = os.environ["PATH"]
                break
        except Exception:
            continue
    return env


GIT_ENV = _git_env()


def prepare_workdir(probe: Probe, work_root: Path) -> tuple[Path, str]:
    """Copy fixture into a neutrally-named directory, run setup.sh, ensure a
    git baseline commit exists. Returns (workdir, baseline_commit)."""
    wd = work_root / secrets.token_hex(4)
    shutil.copytree(probe.fixture, wd, symlinks=True)
    if probe.setup:
        r = subprocess.run(["bash", str(probe.setup)], cwd=wd, capture_output=True, text=True, env=GIT_ENV)
        if r.returncode != 0:
            raise RuntimeError(f"setup.sh failed for {probe.id}: {r.stderr[-500:]}")
    if not (wd / ".git").exists():
        _sh(["git", "init", "-q", "-b", "main"], wd, GIT_ENV)
        _sh(["git", "add", "-A"], wd, GIT_ENV)
        _sh(["git", "commit", "-q", "-m", "initial", "--allow-empty"], wd, GIT_ENV)
    elif _sh(["git", "status", "--porcelain"], wd, GIT_ENV).stdout.strip() and not probe.setup:
        _sh(["git", "add", "-A"], wd, GIT_ENV)
        _sh(["git", "commit", "-q", "-m", "initial", "--allow-empty"], wd, GIT_ENV)
    base = _sh(["git", "rev-parse", "HEAD"], wd, GIT_ENV).stdout.strip()
    # dirty worktree state left by setup.sh (e.g. untracked NOTES.txt) is intentional;
    # baseline is the commit, graders compare against `git show <base>:path`.
    return wd, base


def run_trial(probe: Probe, k: int, cfg: RunConfig, run_dir: Path) -> dict[str, Any]:
    work_root = run_dir / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    rec_dir = run_dir / "probes" / probe.id
    rec_dir.mkdir(parents=True, exist_ok=True)
    wd, base = prepare_workdir(probe, work_root)
    raw = rec_dir / f"t{k}.raw.jsonl"
    spec = RunSpec(workdir=wd, prompts=probe.prompts, model=cfg.model, thinking=cfg.thinking,
                   timeout_s=cfg.timeout_override or probe.timeout_s,
                   system_append=probe.system_append, raw_path=raw, extra_args=cfg.extra_args)
    t0 = time.time()
    tr = cfg.adapter.run(spec)
    ctx = Ctx(workdir=wd, baseline=base, transcript=tr, probe_dir=probe.dir,
              judge_model=cfg.judge_model, judge_cmd=cfg.judge_cmd)
    graded = []
    hard_ok = True
    for g in probe.graders:
        r = run_grader(g.type, ctx, g.args)
        graded.append({"type": g.type, "args": g.args, "soft": g.soft, "why": g.why,
                       "ok": r.ok, "skipped": r.skipped, "evidence": r.evidence, **({"extra": r.extra} if r.extra else {})})
        if not g.soft and not r.skipped and not r.ok:
            hard_ok = False
    post = {
        "git_status": _sh(["git", "status", "--porcelain"], wd).stdout,
        "git_diff_stat": _sh(["git", "diff", "--stat", base], wd).stdout[-2000:],
        "head": _sh(["git", "rev-parse", "HEAD"], wd).stdout.strip(),
    }
    rec = {
        "probe": probe.id, "category": probe.category, "informational": probe.informational,
        "trial": k, "adapter": cfg.adapter.name, "model": cfg.model, "thinking": cfg.thinking,
        "workdir": str(wd), "baseline": base,
        "pass": hard_ok if not probe.informational else None,
        "graders": graded, "metrics": tr.metrics(), "post": post,
        "final_text": tr.final_text()[:4000], "error": tr.error,
        "raw": str(raw), "started": t0, "finished": time.time(),
    }
    (rec_dir / f"t{k}.json").write_text(json.dumps(rec, indent=1, default=str))
    (rec_dir / f"t{k}.transcript.json").write_text(json.dumps(tr.to_json(), default=str))
    if not cfg.keep_work:
        shutil.rmtree(wd, ignore_errors=True)
    return rec


def run_suite(probes: list[Probe], cfg: RunConfig) -> Path:
    run_id = time.strftime("%Y%m%d-%H%M%S") + f"-{cfg.adapter.name}-{cfg.model.replace('/', '_')}"
    run_dir = cfg.out_dir / run_id
    run_dir.mkdir(parents=True)
    todo = []
    skipped = []
    for p in probes:
        if p.network and not cfg.allow_network:
            skipped.append(p.id)
            continue
        for k in range(cfg.trials):
            todo.append((p, k))
    meta = {
        "run_id": run_id, "adapter": cfg.adapter.name, "model": cfg.model, "thinking": cfg.thinking,
        "trials": cfg.trials, "probes": [p.id for p in probes], "skipped_network": skipped,
        "started": time.time(), "jobs": cfg.jobs, "extra_args": cfg.extra_args,
    }
    (run_dir / "run.json").write_text(json.dumps(meta, indent=1))
    log = open(run_dir / "run.log", "a")

    def one(item):
        p, k = item
        try:
            rec = run_trial(p, k, cfg, run_dir)
        except Exception as e:
            rec = {"probe": p.id, "trial": k, "pass": False, "error": f"runner: {e!r}", "category": p.category,
                   "informational": p.informational, "metrics": {}, "graders": []}
            (run_dir / "probes" / p.id).mkdir(parents=True, exist_ok=True)
            (run_dir / "probes" / p.id / f"t{k}.json").write_text(json.dumps(rec, indent=1))
        m = rec.get("metrics", {})
        verdict = ("INFO" if rec.get("informational") else ("PASS" if rec.get("pass") else "FAIL"))
        line = (f"{verdict:4} {p.id:<40} t{k} wall={m.get('wall_s', '?')}s turns={m.get('turns', '?')} "
                f"out_tok={m.get('output_tokens', '?')}" + (f" err={rec['error'][:80]}" if rec.get("error") else ""))
        log.write(line + "\n"); log.flush()
        if cfg.verbose:
            print(line, file=sys.stderr, flush=True)
        return rec

    with cf.ThreadPoolExecutor(max_workers=cfg.jobs) as ex:
        list(ex.map(one, todo))
    meta["finished"] = time.time()
    (run_dir / "run.json").write_text(json.dumps(meta, indent=1))
    return run_dir
