#!/usr/bin/env python3
"""Create a copy-only V2 project-memory archive without external dependencies."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def safe_tree(root: Path) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"Unsafe or missing directory: {root}")
    files: list[Path] = []
    for base, directories, names in os.walk(root, followlinks=False):
        base_path = Path(base)
        for name in directories + names:
            candidate = base_path / name
            if candidate.is_symlink():
                raise ValueError(f"Symlink source is not allowed: {candidate}")
        files.extend(base_path / name for name in names)
    return sorted(files)


def contains(parent: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(parent)
        return True
    except ValueError:
        return False


def archive(project_root: Path, archive_root: Path, now: datetime | None = None) -> Path:
    source = project_root.expanduser().resolve()
    destination_root = archive_root.expanduser().resolve()
    if not source.is_dir() or source.is_symlink():
        raise ValueError(f"Unsafe or missing project root: {project_root}")
    if contains(source, destination_root):
        raise ValueError("archive_root must be outside project_root")
    memory = source / ".vibe"
    if not memory.exists():
        raise ValueError("Missing .vibe directory; nothing to archive")
    memory_files = safe_tree(memory)
    agents = source / "AGENTS.md"
    if agents.exists() and (agents.is_symlink() or not agents.is_file()):
        raise ValueError(f"Unsafe AGENTS.md: {agents}")
    if not agents.exists() and not memory_files:
        raise ValueError("No archiveable V2 project memory")

    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    parent = destination_root / source.name
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / stamp
    suffix = 1
    while target.exists():
        suffix += 1
        target = parent / f"{stamp}-{suffix}"
    staging = parent / f".{target.name}-{uuid.uuid4().hex}.tmp"
    try:
        staging.mkdir()
        copied: list[dict[str, str]] = []
        if agents.exists():
            shutil.copy2(agents, staging / "AGENTS.md")
            copied.append({"path": "AGENTS.md", "sha256": digest(staging / "AGENTS.md")})
        shutil.copytree(memory, staging / ".vibe", symlinks=False)
        for file in sorted((staging / ".vibe").rglob("*")):
            if file.is_file():
                copied.append({"path": file.relative_to(staging).as_posix(), "sha256": digest(file)})
        manifest = {
            "format": "vibe-v2-project-archive-1",
            "created_at": (now or datetime.now(timezone.utc)).isoformat(),
            "source": str(source),
            "files": copied,
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for entry in copied:
            archived = staging / entry["path"]
            if not archived.is_file() or digest(archived) != entry["sha256"]:
                raise ValueError(f"Archive validation failed: {entry['path']}")
        staging.rename(target)
        return target
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


# Publishing a snapshot to Git -------------------------------------------------
#
# A snapshot only becomes durable once it is pushed: a local commit dies with the
# machine. These helpers drive the standard `git` executable (no library, no new
# dependency), never touch the source project, never pass credentials on a command
# line, and never rewrite history.

EXIT_PUSH_FAILED = 4


def run_git(arguments: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run git in `cwd`; return (returncode, stdout, stderr) as stripped text."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(cwd), *arguments],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return 1, "", f"{type(error).__name__}: {error}"
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def publishing_repository(target: Path) -> tuple[Path | None, str]:
    """Return (work-tree root, snapshot path relative to it) when the archive root is Git-managed."""
    code, output, _ = run_git(["rev-parse", "--show-toplevel"], target)
    if code != 0 or not output:
        return None, ""
    repository = Path(output).resolve()
    try:
        return repository, target.resolve().relative_to(repository).as_posix()
    except ValueError:
        return None, ""


def choose_remote(repository: Path, requested: str | None) -> str | None:
    if requested:
        return requested
    _, output, _ = run_git(["remote"], repository)
    remotes = [line for line in output.splitlines() if line.strip()]
    if not remotes:
        return None
    return "origin" if "origin" in remotes else remotes[0]


def remote_head(repository: Path, remote: str, branch: str) -> str | None:
    code, output, _ = run_git(["ls-remote", "--heads", remote, branch], repository)
    if code != 0 or not output:
        return None
    return output.split()[0]


def push(target: Path, remote: str | None = None, message: str | None = None) -> dict[str, str]:
    """Commit and push one snapshot, then confirm the remote ref matches the local commit.

    Returns a report dict. `status` is one of:
      not-a-repository, no-remote, detached-head, already-published, pushed
    Raises ValueError only for an unrecoverable Git state.
    """
    repository, relative = publishing_repository(target)
    if repository is None:
        return {"status": "not-a-repository", "snapshot": str(target)}

    chosen = choose_remote(repository, remote)
    if chosen is None:
        return {"status": "no-remote", "repository": str(repository), "snapshot": relative}

    code, branch, error = run_git(["symbolic-ref", "--short", "HEAD"], repository)
    if code != 0 or not branch:
        return {"status": "detached-head", "repository": str(repository), "snapshot": relative}

    run_git(["add", "-A", "--", relative], repository)
    staged_code, _, staged_error = run_git(["diff", "--cached", "--quiet", "--", relative], repository)
    if staged_code not in (0, 1):
        raise ValueError(f"cannot inspect staged snapshot: {staged_error}")

    commit_note = message or f"archive: {Path(relative).parent.name} {Path(relative).name}"
    if staged_code == 1:
        added, stdout, error = run_git(["commit", "-q", "-m", commit_note, "--", relative], repository)
        if added != 0:
            raise ValueError(f"cannot commit archive snapshot: {error or stdout}")
        commit = run_git(["rev-parse", "HEAD"], repository)[1]
        outcome = "pushed"
    else:
        if run_git(["ls-files", "--error-unmatch", relative], repository)[0] != 0:
            raise ValueError(
                f"archive repository ignores {relative}; remove it from .gitignore so the snapshot can be published"
            )
        commit = run_git(["rev-parse", "HEAD"], repository)[1]
        outcome = "already-published"

    pushed, _, push_error = run_git(["push", "-q", chosen, f"HEAD:{branch}"], repository)
    if pushed != 0:
        # Someone else pushed first: integrate once, then retry. Never force.
        run_git(["fetch", "-q", chosen, branch], repository)
        rebased, _, rebase_error = run_git(["rebase", "-q", f"{chosen}/{branch}"], repository)
        if rebased != 0:
            run_git(["rebase", "--abort"], repository)
            raise ValueError(f"cannot integrate with {chosen}/{branch}: {rebase_error or push_error}")
        commit = run_git(["rev-parse", "HEAD"], repository)[1]
        pushed, _, push_error = run_git(["push", "-q", chosen, f"HEAD:{branch}"], repository)
        if pushed != 0:
            raise ValueError(f"cannot push archive snapshot to {chosen}/{branch}: {push_error}")

    published = remote_head(repository, chosen, branch)
    if published != commit:
        raise ValueError(f"push not confirmed: {chosen}/{branch} is {published}, local is {commit}")

    return {
        "status": outcome,
        "repository": str(repository),
        "snapshot": relative,
        "remote": chosen,
        "branch": branch,
        "commit": commit,
    }



# The remembered archive root lives next to this Skill in the *installed* copy
# (~/.config/opencode/skills/a-project-archive/archive_root.conf). It is user data:
# the installer never ships it, so reinstall/uninstall leave it alone.
CONFIG_FILE = Path(__file__).resolve().parent.parent / "archive_root.conf"
EXIT_UNCONFIGURED = 3


def load_archive_root(config_file: Path | None = None) -> Path | None:
    config_file = config_file or CONFIG_FILE
    try:
        value = config_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return Path(value) if value else None


def save_archive_root(root: Path, config_file: Path | None = None) -> Path:
    config_file = config_file or CONFIG_FILE
    resolved = root.expanduser()
    if not resolved.is_absolute():
        raise ValueError(f"archive root must be an absolute path: {root}")
    resolved = resolved.resolve()
    if not resolved.is_dir():
        raise ValueError(f"archive root does not exist or is not a directory: {resolved}")
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(str(resolved) + "\n", encoding="utf-8")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, help="project to archive (required unless only setting the root)")
    parser.add_argument("--archive-root", type=Path, help="one-off destination; overrides the remembered root without saving it")
    parser.add_argument("--set-archive-root", type=Path, metavar="PATH", help="remember PATH as the default archive root for this machine")
    parser.add_argument("--show-archive-root", action="store_true", help="print the remembered archive root and exit")
    parser.add_argument("--remote", default=None, help="Git remote to push to (default: origin, else the only remote)")
    parser.add_argument("--no-push", action="store_true", help="skip the mandatory publish step (destructive escape hatch; the snapshot then exists only on this machine)")
    args = parser.parse_args()
    try:
        if args.show_archive_root:
            root = load_archive_root()
            print(json.dumps({"archive_root": str(root) if root else None, "config": str(CONFIG_FILE)}, ensure_ascii=False))
            return 0 if root else EXIT_UNCONFIGURED
        if args.set_archive_root is not None:
            saved = save_archive_root(args.set_archive_root)
            print(json.dumps({"archive_root": str(saved), "config": str(CONFIG_FILE)}, ensure_ascii=False))
            if args.project_root is None:
                return 0
        if args.project_root is None:
            parser.error("--project-root is required to archive")
        root = args.archive_root or load_archive_root()
        if root is None:
            print(
                "[!] No archive root is configured and none was given. Ask the user for the absolute archive "
                f"directory, then run again with --set-archive-root <path> (saved to {CONFIG_FILE}).",
                file=sys.stderr,
            )
            return EXIT_UNCONFIGURED
        target = archive(args.project_root, root)
        # Archiving is not finished until the snapshot is pushed: a local commit
        # does not survive the machine. Only an explicit --no-push skips this.
        report: dict[str, object] = {"status": "skipped", "reason": "--no-push"}
        if not args.no_push:
            report = push(target, args.remote)
    except (OSError, ValueError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1
    result = {"archive": str(target), "archive_root": str(root), "publish": report}
    if not args.no_push and report.get("status") in {"not-a-repository", "no-remote", "detached-head"}:
        print(json.dumps(result, ensure_ascii=False))
        explanation = {
            "not-a-repository": f"the archive root is not a Git work tree, so the snapshot stays local: {target}",
            "no-remote": "the archive repository has no remote configured, so the snapshot stays local",
            "detached-head": "the archive repository is on a detached HEAD, so the snapshot cannot be published; check out a branch",
        }[str(report["status"])]
        print(
            f"[!] Archive created but NOT pushed: {explanation}. Make the archive root a Git work tree with a "
            "remote (or pass --archive-root to one), then push the snapshot again.",
            file=sys.stderr,
        )
        return EXIT_PUSH_FAILED
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
