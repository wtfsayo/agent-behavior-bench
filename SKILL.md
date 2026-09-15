# agent-behavior-bench

Run behavioral evaluations on LLM coding agents — sycophancy, scheming,
verifier tampering, prompt injection, laziness, context discipline, and more.

## Before you start

1. **Ask the user which agent and model to test.** The bench supports any
   ACP-speaking agent via [acpx](https://github.com/openclaw/acpx). Common
   targets:
   - `devin` (default) — `swe-2`, `swe-2-high`, `swe-2-max`
   - `claude` — `claude-sonnet-4.5`, `claude-opus-4.5`
   - `codex` — `gpt-5.1-codex`, `gpt-5.2-codex`
   - `opencode2 acp` — `opencode/muse-spark-1.3-contributor-free`, etc.
   - Any raw ACP command: `acpx:<cmd with args>`

2. **Check if acpx is installed:**
   ```bash
   which acpx || npm i -g acpx
   ```
   If npm isn't available, check for a local install or ask the user.

3. **Verify the model exists in the harness** before running the full suite:
   ```bash
   # list available models for the agent
   acpx <agent> models 2>/dev/null || <agent-cli> models

   # smoke-test: one fast probe, one trial
   ./abb.py run --adapter acpx:<agent> --model <model> --probes needle-haystack --trials 1 --timeout 60
   ```
   If the model id is wrong, the adapter will error on `session/new` or
   `set_config_option` — fix the id before burning a full run.

4. **Explain what will happen** before running:
   - Each probe drops the agent into a fresh git working copy with a
     deliberately awkward situation
   - The agent's actions are graded deterministically (file state, git state,
     tool-call log, thinking stream)
   - A run of 52 probes × 3 trials takes ~1–3 hours depending on the model
   - Results go to `results/<timestamp>-<adapter>-<model>/`

## Running

```bash
# full suite (52 probes × N trials)
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
