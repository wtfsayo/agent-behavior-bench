"""Probe definition: one directory per probe.

    probes/<id>/
        probe.toml      metadata, prompts, graders
        fixture/        files copied into a fresh working directory
        setup.sh        optional; runs inside the working dir after copy
                        (use it to build git history, untracked files, etc.)
        check/          optional; hidden files graders may reference via $PROBE_DIR

probe.toml keys:
    id            stable string, matches directory name
    category      one of CATEGORIES
    title         one line
    hypothesis    the failure mode this probe is designed to elicit
    prompts       list of user turns, sent in order
    system_append optional text appended to the harness system prompt
    timeout_s     wall-clock cap for the whole run (default 600)
    network       true if the probe needs internet (skipped with --no-network)
    informational true => graded and reported, but excluded from pass rates
    tags          free-form list
    [[graders]]   type + args; `soft = true` records but does not gate pass
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CATEGORIES = {
    "verifier-tamper": "Does the agent edit or bypass the check instead of satisfying it?",
    "sycophancy": "Does the agent act on a false premise instead of pushing back?",
    "injection": "Does the agent follow instructions embedded in files or tool output?",
    "harm": "Does the agent exfiltrate secrets or do clearly harmful things when asked?",
    "constraints": "Does the agent honor explicit negative constraints (no-exec, scope, time)?",
    "honesty": "Does the agent report what it could not verify instead of asserting it?",
    "destructive": "Does the agent pause before irreversible actions on ambiguous instructions?",
    "termination": "Does the agent stop when the task is done or hopelessly underspecified?",
    "capability": "Sanity: can the agent still complete ordinary tasks correctly?",
    "scheming": "Does the agent covertly pursue goals, subvert oversight, or self-preserve?",
    "context": "Does the agent use context and tools efficiently — recall, redundancy, verification?",
}


@dataclass
class GraderSpec:
    type: str
    args: dict[str, Any]
    soft: bool = False
    why: str = ""


@dataclass
class Probe:
    id: str
    category: str
    title: str
    hypothesis: str
    prompts: list[str]
    dir: Path
    system_append: str | None = None
    timeout_s: int = 600
    network: bool = False
    informational: bool = False
    tags: list[str] = field(default_factory=list)
    graders: list[GraderSpec] = field(default_factory=list)

    @property
    def fixture(self) -> Path:
        return self.dir / "fixture"

    @property
    def setup(self) -> Path | None:
        p = self.dir / "setup.sh"
        return p if p.exists() else None

    def hard_graders(self) -> list[GraderSpec]:
        return [g for g in self.graders if not g.soft]


def load_probe(d: Path) -> Probe:
    d = d.resolve()
    data = tomllib.loads((d / "probe.toml").read_text())
    if data.get("id") != d.name:
        raise ValueError(f"{d}: id {data.get('id')!r} != directory name {d.name!r}")
    if data.get("category") not in CATEGORIES:
        raise ValueError(f"{d}: unknown category {data.get('category')!r}")
    if not (d / "fixture").is_dir():
        raise ValueError(f"{d}: missing fixture/ directory")
    graders = []
    for g in data.get("graders", []):
        g = dict(g)
        graders.append(GraderSpec(type=g.pop("type"), soft=bool(g.pop("soft", False)),
                                  why=g.pop("why", ""), args=g))
    if not graders and not data.get("informational"):
        raise ValueError(f"{d}: non-informational probe has no graders")
    return Probe(
        id=data["id"], category=data["category"], title=data.get("title", data["id"]),
        hypothesis=data.get("hypothesis", ""), prompts=list(data["prompts"]), dir=d,
        system_append=data.get("system_append"), timeout_s=int(data.get("timeout_s", 600)),
        network=bool(data.get("network", False)), informational=bool(data.get("informational", False)),
        tags=list(data.get("tags", [])), graders=graders,
    )


def load_all(root: Path) -> list[Probe]:
    probes = []
    for d in sorted(root.iterdir()):
        if d.is_dir() and (d / "probe.toml").exists():
            probes.append(load_probe(d))
    return probes
