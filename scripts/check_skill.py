#!/usr/bin/env python3
"""Check the skill and plugin packaging. Exit 1 and list problems on failure."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "agent-behavior-bench"
SKILL = ROOT / "skills" / NAME / "SKILL.md"


def frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            out[key.strip()] = value.strip()
    return out


def main() -> int:
    errors = []
    text = SKILL.read_text()
    fm = frontmatter(text)
    name = fm.get("name", "")
    desc = fm.get("description", "")
    if name != NAME:
        errors.append(f"SKILL.md name {name!r} must equal its directory name {NAME!r}")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) or len(name) > 64:
        errors.append("SKILL.md name must be lowercase-hyphenated, at most 64 chars")
    if not desc or len(desc) > 1024 or "<" in desc or ">" in desc:
        errors.append("SKILL.md description must be 1-1024 chars without angle brackets")
    if re.search(r"\b\d+ probes\b", text):
        errors.append("SKILL.md hardcodes a probe count; point to `./abb.py list` instead")

    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    if plugin.get("name") != NAME:
        errors.append(f"plugin.json name must be {NAME!r}")
    if not plugin.get("license"):
        errors.append("plugin.json needs a license")
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    if [p.get("name") for p in market.get("plugins", [])] != [NAME]:
        errors.append(f"marketplace.json must list exactly the {NAME!r} plugin")

    for e in errors:
        print(f"FAIL {e}", file=sys.stderr)
    if not errors:
        print("ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
