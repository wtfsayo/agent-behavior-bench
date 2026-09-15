"""Adapter interface.

An adapter knows how to launch one agent CLI in non-interactive mode inside a
working directory, feed it one or more user prompts in sequence, and convert
the CLI's native event stream into a `Transcript`.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..transcript import Transcript


@dataclass
class RunSpec:
    workdir: Path
    prompts: list[str]
    model: str
    thinking: str | None
    timeout_s: int
    system_append: str | None = None
    raw_path: Path | None = None
    extra_args: list[str] = field(default_factory=list)


class Adapter:
    name: str = "base"

    def run(self, spec: RunSpec) -> Transcript:  # pragma: no cover - interface
        raise NotImplementedError

    # -- shared helper ----------------------------------------------------
    @staticmethod
    def _exec(cmd: list[str], cwd: Path, timeout_s: int, stdout_path: Path,
              stdin_text: str | None = None) -> tuple[int | None, bool, float, str]:
        """Run a command, streaming stdout to a file. Returns
        (exit_code, timed_out, wall_s, stderr_tail)."""
        start = time.time()
        timed_out = False
        with open(stdout_path, "wb") as out, open(str(stdout_path) + ".err", "wb") as err:
            proc = subprocess.Popen(
                cmd, cwd=str(cwd), stdout=out, stderr=err,
                stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                proc.communicate(input=stdin_text.encode() if stdin_text is not None else None,
                                 timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_tree(proc)
                try:
                    proc.wait(timeout=10)
                except Exception:
                    pass
        wall = time.time() - start
        try:
            tail = Path(str(stdout_path) + ".err").read_text(errors="replace")[-2000:]
        except Exception:
            tail = ""
        return proc.returncode, timed_out, wall, tail


def _kill_tree(proc: subprocess.Popen) -> None:
    import os
    import signal
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        time.sleep(2)
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
