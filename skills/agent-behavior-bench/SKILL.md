---
name: agent-behavior-bench
description: Run behavioral evals (sycophancy, scheming, verifier tampering, prompt injection, laziness) on ACP coding agents via acpx. Use when asked to benchmark or evaluate an agent's or model's behavior, or to compare bench runs.
---

# agent-behavior-bench

## Before you start

1. **Find the bench root**, the directory that holds `abb.py`. It is two
   levels above this file. Run every `./abb.py` command from there. If
   `abb.py` is not there (the skill was installed without the repo), ask the
   user before cloning `https://github.com/wtfsayo/agent-behavior-bench`.

2. **Ask the user which agent and model to test.** The bench supports any
   ACP-speaking agent via [acpx](https://github.com/openclaw/acpx). Common
   targets:
   - `devin` (default) — `swe-2`, `swe-2-high`, `swe-2-max`
   - `claude` — `claude-sonnet-4.5`, `claude-opus-4.5`
   - `codex` — `gpt-5.1-codex`, `gpt-5.2-codex`
   - `opencode2 acp` — `opencode/muse-spark-1.3-contributor-free`, etc.
   - Any raw ACP command: `acpx:<cmd with args>`

3. **Check that acpx is installed:**
   ```bash
   which acpx
   ```
   If it is missing, ask the user before running `npm i -g acpx`, because it
   is a global install. If they decline or npm is unavailable, ask for the
   path to an existing acpx binary and pass it with `--binary <path>`.

4. **Verify the model exists in the harness** before running the full suite:
   ```bash
   # list available models for the agent
   acpx <agent> models 2>/dev/null || <agent-cli> models

   # smoke-test: one fast probe, one trial
   ./abb.py run --adapter acpx:<agent> --model <model> --probes needle-haystack --trials 1 --timeout 60
   ```
   If the model id is wrong, the adapter will error on `session/new` or
   `set_config_option` — fix the id before burning a full run.

5. **Explain what will happen** before running:
   - Each probe drops the agent into a fresh git working copy with a
     deliberately awkward situation
   - The agent's actions are graded deterministically (file state, git state,
     tool-call log, thinking stream)
   - A full run (every probe in `./abb.py list`) × 3 trials takes ~1–3 hours
     depending on the model
   - Results go to `results/<timestamp>-<adapter>-<model>/` under the bench
     root. When the bench root is an installed plugin, pass `--out <dir>` with
     a directory the user picks, since plugin updates replace the install.

## Running

```bash
# full suite (every probe × N trials)
./abb.py run --model <model> --trials 3 --jobs 4

# specific probes or categories
./abb.py run --model <model> --probes 'lazy-*' 'gate-*' --trials 3
./abb.py run --model <model> --category scheming injection --trials 3

# different agent
./abb.py run --adapter 'acpx:opencode2 acp' --model opencode/muse-spark-1.3-contributor-free --trials 3

# resume an interrupted run
./abb.py run --model <model> --trials 3 --resume results/<run-dir>

# compare two runs
./abb.py report results/<run-a> results/<run-b> -o compare.md
```

## Useful flags

| flag | purpose |
|---|---|
| `--thinking high` | fold reasoning effort into model id (swe-2 → swe-2-high) |
| `--jobs N` | parallel trials (default 4) |
| `--timeout N` | per-probe timeout in seconds (default from probe.toml) |
| `--no-network` | skip probes that need internet |
| `--judge-model <m>` | enable llm_judge graders |
| `--rm-work` | delete working copies after grading |
| `--quiet` | suppress per-trial output |
| `--resume <dir>` | skip completed trials, continue where it left off |
| `--out <dir>` | parent directory for run dirs (default `results/`) |

## Interpreting results

- `report.md` — per-probe pass rates, failure evidence, timing
- `summary.json` — machine-readable aggregate
- `probes/<id>/t<k>.json` — per-trial verdicts, grader evidence, git diff
- `probes/<id>/t<k>.transcript.json` — full transcript with thinking traces
- `probes/<id>/t<k>.raw.jsonl` — raw ACP event stream

**Pass rates are over non-informational probes.** Probes marked
`informational = true` are graded but excluded from the headline number.

## What the categories mean

| category | failure mode |
|---|---|
| verifier-tamper | edits the check instead of satisfying it |
| scheming | covert goals, oversight subversion, self-exfiltration, sandbagging |
| sycophancy | capitulates to wrong user claims, authority pressure |
| injection | follows instructions hidden in files, tool output, AGENTS.md |
| context | re-fetches instead of recalling, doesn't re-verify claimed changes |
| laziness | hardcodes, special-cases, swallows exceptions, deletes tests |
| constraints | ignores "don't run", scope limits, instruction hierarchy |
| honesty | asserts without verifying |
| destructive | irreversible git ops on vague requests |
| termination | invents work when there's nothing left |
| harm | exfiltrates secrets when asked nicely |
| capability | sanity: can it still do ordinary tasks |

## Caveats

- Results are a property of **model × harness** — the same model behind
  different adapters sees different system prompts and tools
- n=3–5 trials shows stable behaviors; use more trials for small differences
- Text graders are regexes — read evidence strings before trusting a
  text-only fail
- Agents sometimes notice they're being probed — random directory names and
  `validate`'s leak-word check reduce but don't eliminate this

## Report back

Build the report from the run dir's `summary.json` (or the `report.md` beside
it). Include:

- Run identity: run dir path, `adapter`, `model`, `thinking`, `trials`.
- Headline: `overall.passed`/`overall.n` and `overall.rate`, noting that it
  excludes informational probes.
- Per-category pass rates from `categories`.
- Every non-informational probe with `passed < n`: its pass count, the hard
  graders in `failing_graders`, and one string from `fail_evidence`. Mark
  failures that come only from text graders as regex-based.
- Probes with nonzero `errors` or `timed_out`, listed separately as harness
  problems rather than agent behavior.
- Probes skipped by `--no-network` (`skipped_network` in `run.json`).

The report is complete when every failing probe in `summary.json` appears in
it with evidence, and the headline matches `overall`.
