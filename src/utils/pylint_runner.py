from __future__ import annotations

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple, Union

from src.utils.file_system import read


_SCORE_RE = re.compile(r"rated at\s+(-?\d+(?:\.\d+)?)/10")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sandbox_root() -> Path:
    return (_repo_root() / "sandbox").resolve()


def _ensure_in_sandbox(path: Path) -> Path:
    sandbox = _sandbox_root()
    resolved = path.resolve()
    if os.path.commonpath([str(resolved), str(sandbox)]) != str(sandbox):
        raise PermissionError("Access outside sandbox is forbidden")
    return resolved


def _collect_py_files(target: Path) -> List[Path]:
    if target.is_file():
        return [target] if target.suffix == ".py" else []
    return sorted(p for p in target.rglob("*.py") if p.is_file())


def run_pylint(target_path: Union[str, Path]) -> Tuple[float, List[str]]:
    repo = _repo_root()
    target = Path(target_path)
    if not target.is_absolute():
        target = (repo / target).resolve()

    target = _ensure_in_sandbox(target)
    files = _collect_py_files(target)

    if not files:
        return 10.0, []

    for f in files:
        read(str(f))

    cmd = [
        sys.executable,
        "-m",
        "pylint",
        "--exit-zero",
        "--reports=n",
        "--persistent=n",
        "--score=y",
        "--msg-template={path}:{line}:{column}: {msg_id} ({symbol}) {msg}",
        *[str(f) for f in files],
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo) + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
    )

    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    lines = [l.strip() for l in output.splitlines() if l.strip()]

    score = 0.0
    for line in reversed(lines):
        m = _SCORE_RE.search(line)
        if m:
            score = float(m.group(1))
            break

    issues = []
    for line in lines:
        if "has been rated at" in line:
            continue
        if re.search(r"\b[A-Z]\d{4}\b", line):
            issues.append(line)

    return score, issues
