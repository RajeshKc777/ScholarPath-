"""Packaging and security invariants that must hold in the source tree (G138).

The packaged app must never carry user data, and the app must always write
its data outside the program folder - including when it runs frozen.
"""

from __future__ import annotations

from pathlib import Path

import scholarpath
from scholarpath.config import app_data_dir, config_path
from scholarpath.logging_setup import log_dir

REPO = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "venv", "dist", "build", "__pycache__", ".pytest_cache"}
FORBIDDEN_NAMES = {
    "config.toml",
    "service.json",
    "credentials.json",
    "accounts.json",
    ".env",
}
FORBIDDEN_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12", ".pfx")


def _package_dir() -> Path:
    return Path(scholarpath.__file__).resolve().parent


def test_user_data_lives_outside_the_program_folder() -> None:
    package = _package_dir()
    for folder in (app_data_dir(), config_path().parent, log_dir()):
        resolved = Path(folder).resolve()
        assert resolved != package
        assert package not in resolved.parents, (
            f"{resolved} is inside the program folder - a frozen app could not "
            "write there"
        )


def test_the_config_file_is_not_inside_the_package() -> None:
    assert _package_dir() not in config_path().resolve().parents


def test_no_user_data_or_secret_files_are_committed() -> None:
    problems: list[str] = []
    for path in REPO.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name.casefold() in FORBIDDEN_NAMES:
            problems.append(str(path.relative_to(REPO)))
        elif path.suffix.casefold() in FORBIDDEN_SUFFIXES:
            problems.append(str(path.relative_to(REPO)))
    assert not problems, f"user data or secret files are committed: {problems}"


def test_the_build_definition_is_part_of_the_project() -> None:
    spec = REPO / "packaging" / "scholarpath.spec"
    assert spec.exists(), "the PyInstaller spec must be committed"
    audit = REPO / "packaging" / "verify_bundle.py"
    assert audit.exists(), "the bundle security audit must be committed"
