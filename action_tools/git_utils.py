"""Shared git utility functions for CI workflows."""

from __future__ import annotations

import shlex
import subprocess
import sys


def run_cmd(
    cmd: list[str],
    *,
    check: bool = True,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run a command, streaming output to the console.

    If *check* is True (default) and the command returns a non-zero exit code,
    the process is terminated immediately.
    """
    print(f"+ {shlex.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=cwd)
    if check and result.returncode != 0:
        print(
            f"\nCommand failed (exit code {result.returncode}): {shlex.join(cmd)}",
            file=sys.stderr,
        )
        sys.exit(1)
    return result


def run_cmd_output(
    cmd: list[str],
    *,
    check: bool = True,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command and capture its stdout/stderr."""
    print(f"+ {shlex.join(cmd)}", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if check and result.returncode != 0:
        if result.stderr:
            sys.stderr.write(result.stderr)
        print(
            f"\nCommand failed (exit code {result.returncode}): {shlex.join(cmd)}",
            file=sys.stderr,
        )
        sys.exit(1)
    return result


def configure_git(cwd: str | None = None) -> None:
    """Configure git with GitHub Actions bot credentials."""
    run_cmd(
        ["git", "config", "user.name", "github-actions[bot]"],
        cwd=cwd,
    )
    run_cmd(
        [
            "git",
            "config",
            "user.email",
            "41898282+github-actions[bot]@users.noreply.github.com",
        ],
        cwd=cwd,
    )


def checkout(branch: str, cwd: str | None = None) -> None:
    """Checkout a branch."""
    run_cmd(["git", "checkout", branch], cwd=cwd)


def is_ancestor(
    ancestor: str,
    descendant: str,
    cwd: str | None = None,
) -> bool:
    """Return True if *ancestor* is an ancestor of *descendant*."""
    result = run_cmd_output(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
        cwd=cwd,
    )
    return result.returncode == 0


def get_commit_hash(ref: str, cwd: str | None = None) -> str:
    """Return the full commit hash of *ref*."""
    result = run_cmd_output(["git", "rev-parse", ref], cwd=cwd)
    return result.stdout.strip()


def merge_branch(
    source: str,
    *,
    message: str | None = None,
    ff_only: bool = False,
    cwd: str | None = None,
) -> None:
    """Merge *source* into the current branch.  Exits on failure."""
    cmd = ["git", "merge", source]
    if ff_only:
        cmd.append("--ff-only")
    if message:
        cmd.extend(["-m", message])
    result = run_cmd(cmd, check=False, cwd=cwd)
    if result.returncode != 0:
        print(
            f"\nFailed to merge '{source}' into current branch.",
            file=sys.stderr,
        )
        sys.exit(1)


def push_branch(branch: str, cwd: str | None = None) -> None:
    """Push *branch* to origin."""
    run_cmd(["git", "push", "origin", branch], cwd=cwd)
