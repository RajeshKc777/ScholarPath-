"""Security check for a built ScholarPath bundle (G207 / G138).

Run after a build:

    .venv\\Scripts\\python.exe packaging\\verify_bundle.py

It fails (exit code 1) when the build folder contains anything that must
never ship: a user config, a database, a log, a credential file, or a secret
that looks like one of ours.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "ScholarPathAI"

# Files that must never be inside a build.
FORBIDDEN_NAMES = {
    "config.toml",
    "service.json",
    "credentials.json",
    "accounts.json",
    ".env",
    "id_rsa",
    "id_ed25519",
}
FORBIDDEN_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key", ".p12", ".pfx")

# Public root certificates that ship with certifi are not secrets.
ALLOWED_NAMES = {"cacert.pem"}

# Secret shapes used by the model services this app talks to.
SECRET_PATTERNS = (
    re.compile(r"oc_sk_[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9]{32,}"),
)
TEXT_SUFFIXES = (".py", ".txt", ".json", ".toml", ".cfg", ".ini", ".md", ".yaml", ".yml")


def main() -> int:
    if not DIST.exists():
        print(f"No build found at {DIST}. Build it first.")
        return 1

    problems: list[str] = []
    files = [path for path in DIST.rglob("*") if path.is_file()]
    print(f"scanning {len(files)} files in {DIST}")

    for path in files:
        name = path.name.casefold()
        if name in ALLOWED_NAMES:
            continue
        if name in FORBIDDEN_NAMES:
            problems.append(f"forbidden file in the bundle: {path.relative_to(DIST)}")
        if path.suffix.casefold() in FORBIDDEN_SUFFIXES:
            problems.append(f"forbidden file type in the bundle: {path.relative_to(DIST)}")

    for path in files:
        if path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                problems.append(
                    f"secret-looking value in {path.relative_to(DIST)}: "
                    f"{match.group(0)[:12]}..."
                )

    # The interpreter must be inside the bundle: the app must not need a
    # system Python to start.
    interpreter = list(DIST.rglob("python3*.dll"))
    if not interpreter:
        problems.append("no bundled Python runtime found - the app would need one installed")

    if problems:
        print("\nFAILED:")
        for problem in problems:
            print("  -", problem)
        return 1

    size = sum(path.stat().st_size for path in files)
    print(f"OK: no user data, no secrets, interpreter bundled ({size / 1e6:.0f} MB).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
