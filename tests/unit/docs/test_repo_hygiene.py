"""Repository hygiene: secrets never tracked or staged, lock covers declared dependencies per package."""

import re
import subprocess
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
_SECRET = re.compile(r"sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")
_BINARY_SUFFIXES = {".pdf", ".png", ".zip", ".pyc"}


def _candidate_files() -> list[Path]:
    """Tracked files plus untracked files that are not ignored: what the next commit could contain."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [REPO / line for line in out.splitlines() if line]


def test_env_files_are_ignored_and_untracked():
    names = {p.name for p in _candidate_files()}
    assert ".env" not in names and not any(n.startswith(".env.") and n != ".env.example" for n in names)
    assert subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=REPO).returncode == 0, ".env must be gitignored"
    assert subprocess.run(["git", "check-ignore", "-q", "uv.lock"], cwd=REPO).returncode == 0, (
        "uv.lock must be gitignored (single lock policy)"
    )


def test_no_secret_patterns_in_tracked_or_stageable_text_files():
    offenders = []
    for path in _candidate_files():
        if path.suffix in _BINARY_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if _SECRET.search(text):
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], f"secret-looking strings found (synthetic test keys must be built at runtime): {offenders}"


def _lock_entries(lock: str) -> dict[str, int]:
    """Map each pinned package to the number of --hash lines that belong to it."""
    entries: dict[str, int] = {}
    current = None
    for line in lock.splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+)==", line)
        if m:
            current = m.group(1).lower().replace("_", "-")
            entries[current] = 0
        elif current and "--hash=sha256:" in line:
            entries[current] += 1
        elif line.strip() and not line.startswith(("#", " ", "\t")):
            current = None
    return entries


def test_lock_pins_every_declared_dependency_with_hashes_per_package():
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    declared = project["dependencies"] + project["optional-dependencies"]["dev"]
    names = {re.split(r"[<>=!~\[ ]", d, maxsplit=1)[0].lower().replace("_", "-") for d in declared}
    entries = _lock_entries((REPO / "requirements.lock").read_text(encoding="utf-8"))
    assert names <= set(entries), f"missing from requirements.lock: {sorted(names - set(entries))}"
    unhashed = sorted(name for name, n in entries.items() if n == 0)
    assert unhashed == [], f"lock entries without a sha256 hash: {unhashed}"
    assert "setuptools" in entries, "build backend must be pinned in the lock"


def test_lock_hash_check_detects_a_missing_hash():
    lock = "pkg-a==1.0 \\\n    --hash=sha256:aa\n\nno-hash==2.0\n\npkg-b==3.0 \\\n    --hash=sha256:bb \\\n    --hash=sha256:cc\n"
    assert _lock_entries(lock) == {"pkg-a": 1, "no-hash": 0, "pkg-b": 2}


def test_build_lock_is_hashed_and_agrees_with_the_main_lock():
    main = _lock_entries((REPO / "requirements.lock").read_text(encoding="utf-8"))
    build_text = (REPO / "requirements-build.lock").read_text(encoding="utf-8")
    build = _lock_entries(build_text)
    assert build.get("setuptools", 0) >= 1, "build lock must pin setuptools with a hash"
    main_version = re.search(r"^setuptools==(\S+)", (REPO / "requirements.lock").read_text(encoding="utf-8"), re.M)
    build_version = re.search(r"^setuptools==(\S+)", build_text, re.M)
    assert main_version and build_version and main_version.group(1) == build_version.group(1), (
        "setuptools must be the same version in both locks"
    )
    assert (REPO / "requirements-build.in").is_file() and main.get("setuptools", 0) >= 1
