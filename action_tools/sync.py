#!/usr/bin/env python3
"""Sync upstream xjb changes into fork branches.

Workflow
--------
1. Fast-forward the ``upstream`` branch to the xjb upstream's ``main``.
2. Merge ``upstream`` → ``main``, run xjb tests, push.
3. Merge ``main`` → ``ssrjson``, run ssrjson integration test, push.

Early exit: if no new upstream commits **and** ``ssrjson`` already contains
everything in ``upstream``, the script exits successfully without pushing.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from typing import Callable

# ---------------------------------------------------------------------------
# Make sure sibling modules are importable regardless of CWD.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_utils import (  # noqa: E402
    checkout,
    configure_git,
    get_commit_hash,
    is_ancestor,
    merge_branch,
    push_branch,
    run_cmd,
)

UPSTREAM_URL = "https://github.com/xjb714/xjb"
SSRJSON_URL = "https://github.com/antares0982/ssrjson"

REPO_DIR = os.environ.get("GITHUB_WORKSPACE", os.getcwd())


# ---------------------------------------------------------------------------
# Step 1 – sync upstream branch
# ---------------------------------------------------------------------------
def sync_upstream_branch() -> bool:
    """Fast-forward ``upstream`` to the xjb remote's ``main``.

    Returns True if new commits were pulled, False otherwise.
    Exits with an error if the fast-forward is not possible.
    """
    print("=== Syncing upstream branch with xjb upstream ===", flush=True)

    run_cmd(["git", "fetch", UPSTREAM_URL, "main"], cwd=REPO_DIR)

    old_hash = get_commit_hash("upstream", cwd=REPO_DIR)
    new_hash = get_commit_hash("FETCH_HEAD", cwd=REPO_DIR)

    if old_hash == new_hash:
        print("No new changes from upstream.", flush=True)
        return False

    # Verify fast-forward is possible
    if not is_ancestor(old_hash, new_hash, cwd=REPO_DIR):
        print(
            "Error: cannot fast-forward 'upstream' branch — "
            "it has diverged from the upstream remote.",
            file=sys.stderr,
        )
        sys.exit(1)

    checkout("upstream", cwd=REPO_DIR)
    merge_branch("FETCH_HEAD", ff_only=True, cwd=REPO_DIR)

    print("upstream branch updated successfully.", flush=True)
    return True


# ---------------------------------------------------------------------------
# Reusable merge → test → push
# ---------------------------------------------------------------------------
def merge_test_push(
    target: str,
    source: str,
    test_fn: Callable[[], None],
) -> None:
    """Checkout *target*, merge *source*, run *test_fn*, then push."""
    print(f"\n=== Merging '{source}' into '{target}' ===", flush=True)
    checkout(target, cwd=REPO_DIR)
    merge_branch(
        source,
        message=f"Merge '{source}' into '{target}'",
        cwd=REPO_DIR,
    )

    print(f"=== Testing '{target}' ===", flush=True)
    test_fn()

    push_branch(target, cwd=REPO_DIR)
    print(f"'{target}' pushed successfully.", flush=True)


# ---------------------------------------------------------------------------
# Test callbacks
# ---------------------------------------------------------------------------
def test_xjb() -> None:
    """Run the xjb test suite (``test.sh``)."""
    run_cmd(["bash", "test.sh"], cwd=REPO_DIR)


def test_ssrjson() -> None:
    """Clone the ssrjson project, patch xjb source, and run its tests."""
    ssrjson_dir = os.path.join(tempfile.gettempdir(), "ssrjson")

    # Clean up any leftover clone
    if os.path.exists(ssrjson_dir):
        shutil.rmtree(ssrjson_dir)

    print("Cloning ssrjson project…", flush=True)
    run_cmd(["git", "clone", SSRJSON_URL, ssrjson_dir])

    # Verify the target file exists
    target = os.path.join(ssrjson_dir, "src", "xjb", "xjb.cpp")
    if not os.path.isfile(target):
        print(
            f"Error: '{target}' does not exist in the ssrjson project.\n"
            "The ssrjson project may have changed its directory structure.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Overwrite with the latest ftoa.cpp
    source_file = os.path.join(REPO_DIR, "src", "ftoa.cpp")
    print(f"Copying {source_file} → {target}", flush=True)
    shutil.copy2(source_file, target)

    # Run ssrjson tests via nix
    print("Running ssrjson tests…", flush=True)
    run_cmd(
        ["nix", "develop", ".#buildenv-py313", "-c", "python", "dev_tools/linux_test.py", "--asan"],
        cwd=ssrjson_dir,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    configure_git(cwd=REPO_DIR)

    # Step 1 — sync upstream branch
    has_updates = sync_upstream_branch()

    # Early exit: nothing new and ssrjson already contains upstream
    if not has_updates and is_ancestor("upstream", "ssrjson", cwd=REPO_DIR):
        print("\nNo upstream updates and ssrjson is up-to-date. Nothing to do.")
        return

    # Push the updated upstream branch (only when it actually changed)
    if has_updates:
        push_branch("upstream", cwd=REPO_DIR)

    # Step 2 — merge upstream → main, test, push
    merge_test_push("main", "upstream", test_xjb)

    # Step 3 — merge main → ssrjson, test with ssrjson project, push
    merge_test_push("ssrjson", "main", test_ssrjson)


if __name__ == "__main__":
    main()
