#!/usr/bin/env python3
"""Update vendored skills from upstream repositories.

Steps:
  1. Clone mattpocock/skills at HEAD into a temp dir
  2. Copy grill-me/ into vendor/skills/grill-me/
  3. Write new SHA to vendor/skills/grill-me/VERSION
  4. Verify LICENSE still matches ATTRIBUTION.md record; fail if license changed
  5. Leave changes as working tree diff for human review (don't auto-commit)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "vendor" / "skills"
ATTRIBUTION_FILE = REPO_ROOT / "ATTRIBUTION.md"

UPSTREAM_REPO = "https://github.com/mattpocock/skills.git"
SKILL_NAME = "grill-me"


def _clone_upstream(dest: Path) -> str:
    """Clone the upstream repo and return the HEAD SHA."""
    subprocess.check_call(
        ["git", "clone", "--depth=1", UPSTREAM_REPO, str(dest)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    sha = subprocess.check_output(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
    ).decode().strip()
    return sha


def _copy_skill(source: Path, dest: Path) -> None:
    """Copy the skill directory, replacing any existing content."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)


def _write_version(dest: Path, sha: str) -> None:
    """Write the SHA to the VERSION file."""
    (dest / "VERSION").write_text(sha + "\n")


def _verify_license(upstream_dir: Path) -> None:
    """Verify the upstream LICENSE is still MIT.

    Reads the LICENSE file from the cloned repo and checks the first line.
    Fails loudly if the license has changed from MIT.
    """
    license_file = upstream_dir / "LICENSE"
    if not license_file.exists():
        print("ERROR: upstream LICENSE file not found", file=sys.stderr)
        sys.exit(1)

    content = license_file.read_text()
    if "MIT License" not in content:
        print(
            "ERROR: upstream license has changed from MIT. "
            "Update ATTRIBUTION.md and review before proceeding.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Cross-check against ATTRIBUTION.md
    if ATTRIBUTION_FILE.exists():
        attr_content = ATTRIBUTION_FILE.read_text()
        if "MIT" not in attr_content:
            print(
                "ERROR: ATTRIBUTION.md does not mention MIT license. "
                "Update ATTRIBUTION.md to match upstream.",
                file=sys.stderr,
            )
            sys.exit(1)


def main() -> None:
    """Entry point."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "upstream"
        print(f"Cloning {UPSTREAM_REPO} ...")
        sha = _clone_upstream(tmp_path)
        print(f"Upstream HEAD: {sha}")

        skill_src = tmp_path / SKILL_NAME
        if not skill_src.is_dir():
            print(f"ERROR: {SKILL_NAME}/ not found in upstream repo", file=sys.stderr)
            sys.exit(1)

        # Verify license before copying
        print("Verifying license ...")
        _verify_license(tmp_path)

        # Copy and write VERSION
        skill_dest = VENDOR_DIR / SKILL_NAME
        print(f"Copying {SKILL_NAME}/ -> {skill_dest.relative_to(REPO_ROOT)} ...")
        _copy_skill(skill_src, skill_dest)
        _write_version(skill_dest, sha)

        print(f"Updated {SKILL_NAME} to {sha}")
        print()
        print("Changes are in your working tree. Review with:")
        print(f"  git diff -- {VENDOR_DIR.relative_to(REPO_ROOT)}/")
        print()
        print("Remember to update manifests/grill/me.yaml attribution.commit_sha")
        print("and ATTRIBUTION.md if the SHA changed.")


if __name__ == "__main__":
    main()
