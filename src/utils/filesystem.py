from pathlib import Path
from typing import Dict, List

# Absolute, resolved sandbox root
SANDBOX_ROOT = (Path(__file__).parent.parent.parent / "sandbox").resolve()


class SandboxViolationError(PermissionError):
    """Raised when attempting to access files outside the sandbox."""


def _resolve_and_validate(path: str | Path) -> Path:
    """
    Resolve a path and ensure it is inside the sandbox.
    """
    candidate = Path(path)

    # Force relative paths to be sandbox-relative
    if not candidate.is_absolute():
        candidate = SANDBOX_ROOT / candidate

    resolved = candidate.resolve()

    if not str(resolved).startswith(str(SANDBOX_ROOT)):
        raise SandboxViolationError(
            f"Access denied. Path '{resolved}' is outside the sandbox."
        )

    return resolved


# ---------- Read operations ----------

def read_file(file_path: str | Path) -> str:
    """
    Read a single file from the sandbox.
    """
    path = _resolve_and_validate(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not path.is_file():
        raise IsADirectoryError(f"Expected a file, got directory: {path}")

    return path.read_text(encoding="utf-8")


def list_py_files(dir_path: str | Path) -> List[Path]:
    """
    Recursively list all Python files under a sandbox directory.
    """
    path = _resolve_and_validate(dir_path)

    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {path}")

    if not path.is_dir():
        raise NotADirectoryError(f"Expected a directory, got file: {path}")

    return sorted(p for p in path.rglob("*.py") if p.is_file())


def read_all_py_files(dir_path: str | Path) -> Dict[Path, str]:
    """
    Read all Python files under a directory.
    Returns a mapping: Path -> file content.
    """
    files = list_py_files(dir_path)
    return {file: file.read_text(encoding="utf-8") for file in files}


# ---------- Write operations ----------

def write_file(file_path: str | Path, content: str) -> None:
    """
    Write content to a file inside the sandbox.
    Creates parent directories if needed.
    """
    path = _resolve_and_validate(file_path)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
