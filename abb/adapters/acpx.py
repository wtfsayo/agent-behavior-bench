"""Adapter for `acpx` — headless client for the Agent Client Protocol.

The only adapter: acpx drives every ACP agent uniformly. The adapter name
selects the agent:

  acpx              -> acpx's default agent (codex)
  acpx:claude       -> named acpx agent subcommand
  acpx:devin        -> alias for raw agent command `devin acp`
  acpx:<cmd with args or path>  -> raw ACP server command via `acpx --agent`

Each probe run gets a named acpx session (`sessions new` -> optional
`set model` -> `prompt -s` per user turn -> `sessions close`), so multi-turn
probes share context.

Event mapping (ACP `session/update` notifications):
  agent_thought_chunk  -> Turn.thinking
  agent_message_chunk  -> Turn.text
  tool_call            -> ToolCall(name, args=rawInput)
  tool_call_update     -> ToolCall.result / is_error
  usage_update         -> Turn.input_tokens/output_tokens
  prompt result.usage  -> Turn.input_tokens/output_tokens (fallback/override)
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from .base import Adapter, RunSpec
from ..transcript import Transcript, Turn, ToolCall

# adapter-name suffix -> raw ACP server command (for agents acpx has no
# built-in subcommand for)
RAW_AGENTS = {
    "devin": "devin acp",
}


class AcpxAdapter(Adapter):
    name = "acpx"

    def __init__(self, binary: str = "acpx", agent: str | None = None):
        self.binary = binary
        self.agent = agent  # acpx agent name, raw command, or None (default)

    # -- argv helpers --------------------------------------------------------
    def _base(self, spec: RunSpec) -> list[str]:
        # realpath: acpx's fs bridge rejects paths outside cwd; on macOS the
        # agent emits /private/tmp/... while Python's tmpdir is /tmp/...
        return [self.binary, "--format", "json", "--cwd",
                os.path.realpath(str(spec.workdir))]

    def _agent_argv(self) -> list[str]:
        if not self.agent:
            return []
        raw = RAW_AGENTS.get(self.agent, self.agent)
        if " " in raw or raw.startswith((".", "/")):
            return ["--agent", raw]
        return [raw]

    def _acpx(self, spec: RunSpec, argv: list[str], timeout: int,
              out: Path) -> dict | None:
        """Lifecycle call (sessions new/close, set). Returns last JSON line."""
        cmd = self._base(spec) + self._agent_argv() + argv
        try:
            with open(out, "wb") as f:
                r = subprocess.run(cmd, cwd=os.path.realpath(str(spec.workdir)),
                                   stdout=f,
                                   stderr=subprocess.DEVNULL,
                                   stdin=subprocess.DEVNULL, timeout=timeout)
            last = None
            for line in out.read_text(errors="replace").splitlines():
                try:
                    last = json.loads(line)
                except Exception:
                    pass
            return last
        except Exception:
            return None

    # -- run -----------------------------------------------------------------
    def run(self, spec: RunSpec) -> Transcript:
        raw = spec.raw_path or (spec.workdir / ".abb-raw.jsonl")
        tr = Transcript(adapter=f"acpx:{self.agent or 'default'}",
                        model=spec.model, thinking=spec.thinking)
        start = time.time()
        session = f"abb-{os.getpid()}-{int(start * 1000) % 10_000_000}"
        deadline = start + spec.timeout_s
        parts: list[Path] = []
        # lifecycle logs live outside the workdir so the agent never sees
        # harness bookkeeping files
        logdir = raw.parent

        self._acpx(spec, ["sessions", "new", "--name", session],
                   timeout=30, out=logdir / f"{raw.name}.new.jsonl")

        model = spec.model
        if spec.thinking and model and not model.endswith(f"-{spec.thinking}"):
            # devin-style ids fold effort into the model name (swe-2-high);
            # try the suffixed id first, fall back if the agent rejects it
            r = self._acpx(spec, ["set", "-s", session, "model",
                                  f"{model}-{spec.thinking}"],
                           timeout=60, out=logdir / f"{raw.name}.model.jsonl")
            if r and r.get("action") == "model_set":
                model = f"{model}-{spec.thinking}"
                tr.model = model
            else:
                self._acpx(spec, ["set", "-s", session, "model", model],
                           timeout=60,
                           out=logdir / f"{raw.name}.model.jsonl")
        elif model:
            self._acpx(spec, ["set", "-s", session, "model", model],
                       timeout=60, out=logdir / f"{raw.name}.model.jsonl")

        for i, prompt in enumerate(spec.prompts):
            remaining = deadline - time.time()
            if remaining <= 5:
                tr.timed_out = True
                break
            part = raw.with_suffix(f".{i}.jsonl")
            parts.append(part)
            code, timed_out = self._run_prompt(spec, session, prompt,
                                               remaining, part, tr)
            tr.exit_code = code
            if timed_out:
                tr.timed_out = True
                break
            if tr.error:
                break

        self._acpx(spec, ["sessions", "close", session], timeout=15,
                   out=logdir / f"{raw.name}.close.jsonl")
        tr.wall_s = time.time() - start
        with open(raw, "w") as out:
            for p in parts:
                try:
                    out.write(p.read_text(errors="replace"))
                except Exception:
                    pass
        tr.raw_path = str(raw)
        return tr

    def _run_prompt(self, spec: RunSpec, session: str, prompt: str,
                    timeout_s: float, raw: Path,
                    tr: Transcript) -> tuple[int | None, bool]:
        """One `acpx ... prompt -s <session>` call; stream JSON-RPC lines into
        `raw` while folding events into `tr` (streaming needed for TTFT)."""
        cmd = (self._base(spec) + ["--approve-all"] + self._agent_argv()
               + ["prompt", "-s", session])
        if spec.extra_args:
            cmd += spec.extra_args
        cmd.append(prompt)

        proc = subprocess.Popen(cmd, cwd=os.path.realpath(str(spec.workdir)),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        timed_out = False

        def kill():
            nonlocal timed_out
            timed_out = True
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        timer = threading.Timer(timeout_s, kill)
        timer.start()
        t0 = time.time()
        tr.turns.append(Turn(role="user", text=prompt))
        turn = Turn(role="assistant")
        tr.turns.append(turn)
        by_id: dict[str, ToolCall] = {}
        try:
            with open(raw, "wb") as f:
                assert proc.stdout is not None
                for line in proc.stdout:
                    f.write(line)
                    f.flush()
                    self._handle_line(line, turn, by_id, tr, t0)
        finally:
            timer.cancel()
            try:
                proc.wait(timeout=10)
            except Exception:
                kill()
        err_tail = ""
        try:
            err_tail = (proc.stderr.read().decode(errors="replace")[-2000:]
                        if proc.stderr else "")
        except Exception:
            pass
        if tr.error is None and proc.returncode not in (0, None) \
                and not turn.text and not turn.tool_calls:
            tr.error = err_tail.strip()[-500:] or f"exit {proc.returncode}"
        return proc.returncode, timed_out

    # -- stream parsing ------------------------------------------------------
    def _handle_line(self, line: bytes, turn: Turn, by_id: dict[str, ToolCall],
                     tr: Transcript, t0: float) -> None:
        try:
            ev = json.loads(line)
        except Exception:
            return
        if "error" in ev and ev.get("id") is not None:
            msg = ev["error"]
            tr.error = (msg.get("message") if isinstance(msg, dict)
                        else str(msg))[:500]
            turn.stop_reason = "error"
            return
        res = ev.get("result")
        if isinstance(res, dict) and "stopReason" in res:
            turn.stop_reason = res.get("stopReason")
            usage = res.get("usage") or {}
            if isinstance(usage.get("inputTokens"), (int, float)):
                turn.input_tokens = int(usage["inputTokens"])
            if isinstance(usage.get("outputTokens"), (int, float)):
                turn.output_tokens = int(usage["outputTokens"])
            return
        upd = (ev.get("params") or {}).get("update") or {}
        kind = upd.get("sessionUpdate")
        if not kind:
            return
        if kind == "agent_thought_chunk":
            turn.thinking += _chunk_text(upd)
        elif kind == "agent_message_chunk":
            turn.text += _chunk_text(upd)
        elif kind == "tool_call":
            meta = upd.get("_meta") or {}
            tc = ToolCall(
                id=upd.get("toolCallId"),
                # inferenceToolName = the agent's native tool name (exec, read,
                # edit); fall back to the ACP kind (execute, read, edit)
                name=(meta.get("cognition.ai/inferenceToolName")
                      or upd.get("kind") or "tool"),
                args=upd.get("rawInput") or _args_from_content(upd),
            )
            by_id[tc.id or str(len(turn.tool_calls))] = tc
            turn.tool_calls.append(tc)
        elif kind == "tool_call_update":
            tc = by_id.get(upd.get("toolCallId") or "")
            if tc is not None:
                if upd.get("status") in ("failed", "error"):
                    tc.is_error = True
                out = upd.get("rawOutput")
                if out is not None:
                    tc.result = (out if isinstance(out, str)
                                 else json.dumps(out))[:4000]
                elif upd.get("content"):
                    tc.result = _content_text(upd["content"])[:4000]
        elif kind == "usage_update":
            meta = upd.get("_meta") or {}
            inp = meta.get("cognition.ai/inputTokens")
            outp = meta.get("cognition.ai/outputTokens")
            if isinstance(inp, (int, float)):
                turn.input_tokens = int(inp)
            elif isinstance(upd.get("used"), (int, float)):
                turn.input_tokens = int(upd["used"])
            if isinstance(outp, (int, float)):
                turn.output_tokens = int(outp)
            return
        else:
            return
        if turn.ttft_ms is None:
            turn.ttft_ms = (time.time() - t0) * 1000



def _content_text(content: list) -> str:
    """ACP tool content items nest as {type:'content', content:{type:'text',
    text:...}} or carry a resource {type:'resource', resource:{text:...}}."""
    out = []
    for c in content or []:
        if not isinstance(c, dict):
            continue
        inner = c.get("content")
        if isinstance(inner, dict):
            if inner.get("type") == "text":
                out.append(inner.get("text", ""))
            elif isinstance(inner.get("resource"), dict):
                out.append(inner["resource"].get("text", ""))
        elif c.get("type") == "text":
            out.append(c.get("text", ""))
    return "\n".join(t for t in out if t)


def _args_from_content(upd: dict) -> dict:
    """When rawInput is absent, recover the command from the shell-preview
    resource embedded in the tool_call content."""
    for c in upd.get("content") or []:
        if not isinstance(c, dict):
            continue
        inner = c.get("content") or {}
        res = inner.get("resource") or {}
        if isinstance(res, dict) and res.get("text"):
            return {"command": res["text"]}
    return {}


def _chunk_text(upd: dict) -> str:
    c = upd.get("content")
    if isinstance(c, dict):
        return c.get("text", "")
    if isinstance(c, str):
        return c
    return ""
