#!/usr/bin/env python3
"""Create a copy-only V2 project-memory archive without external dependencies."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
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


# Defense in depth, not a proof of absence of secrets. Never print matched content.
SECRET_NAME = re.compile(r"(^\.env(?:\.|$)|^\.npmrc$|^\.pypirc$|^credentials(?:\.|$)|^auth\.json$|^service-account|^id_(?:rsa|ed25519)|\.(?:pem|key|p12|pfx)$)", re.I)
SECRET_CONTENT = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{12,})\b", re.I)
SECRET_HINT = re.compile(r"(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*[\"']?(?:Bearer\s+)?[A-Za-z0-9+/=_-]{24,}", re.I)


def check_sensitive(file: Path, relative: Path, warnings: list[dict[str, str]] | None = None) -> None:
    if not file.is_file() or any(SECRET_NAME.search(part) for part in relative.parts):
        raise ValueError(f"Unsafe/sensitive archive path: {relative}; sanitize before archiving")
    try:
        text = file.read_text(encoding="utf-8")
    except UnicodeError:
        if warnings is not None:
            warnings.append({"path": relative.as_posix(), "reason": "non-UTF-8 or binary; not scanned"})
        return
    if "\x00" in text or SECRET_CONTENT.search(text):
        raise ValueError(f"Possible secret in archive input: {relative}; sanitize before archiving")
    if warnings is not None and SECRET_HINT.search(text):
        warnings.append({"path": relative.as_posix(), "reason": "credential-like assignment needs manual review"})


def check_snapshot(target: Path, warnings: list[dict[str, str]] | None = None) -> None:
    files = safe_tree(target)
    for file in files:
        check_sensitive(file, file.relative_to(target), warnings)
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    actual = {file.relative_to(target).as_posix(): digest(file) for file in files if file != target / "manifest.json"}
    expected = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    if actual != expected:
        raise ValueError("Archive snapshot no longer matches its manifest")


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

    warnings: list[dict[str, str]] = []
    for file in memory_files:
        check_sensitive(file, file.relative_to(source), warnings)
    if agents.exists():
        check_sensitive(agents, Path("AGENTS.md"), warnings)

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
        check_snapshot(staging, warnings)
        staging.rename(target)
        if warnings:
            unique = {(item["path"], item["reason"]): item for item in warnings}
            print(f"[!] {len(unique)} file(s) need manual review before publishing:", file=sys.stderr)
            for item in unique.values():
                print(f"    {item['path']}: {item['reason']}", file=sys.stderr)
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

# Windows opens a console window for every child process unless it is suppressed,
# which makes an interactive archive flash a black box per git call.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_git(arguments: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run git in `cwd`; return (returncode, stdout, stderr) as stripped text."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(cwd), *arguments],
            capture_output=True,
            text=True,
            timeout=300,
            creationflags=_NO_WINDOW,
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
    _, output, _ = run_git(["remote"], repository)
    remotes = [line for line in output.splitlines() if line.strip()]
    if requested:
        if requested not in remotes:
            raise ValueError("Requested remote is not a configured remote name")
        return requested
    if not remotes:
        return None
    if "origin" in remotes:
        return "origin"
    if len(remotes) != 1:
        raise ValueError("Multiple archive remotes; select one explicitly")
    return remotes[0]


def remote_head(repository: Path, remote: str, branch: str) -> str | None:
    code, output, error = run_git(["ls-remote", "--exit-code", "--heads", remote, f"refs/heads/{branch}"], repository)
    if code == 2:
        return None
    if code != 0 or not output:
        raise ValueError("Could not verify the remote branch; no push attempted")
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

    check_snapshot(target)
    head_code, head, _ = run_git(["rev-parse", "HEAD"], repository)
    if head_code != 0 or not head:
        raise ValueError("Archive repository must have an existing published baseline commit")
    remote_commit = remote_head(repository, chosen, branch)
    if remote_commit is None:
        raise ValueError("Archive branch is not published; publish its baseline explicitly first")
    if head != remote_commit:
        # A retry is safe only when the one unpublished commit is exactly this snapshot.
        _, parents, _ = run_git(["rev-list", "--parents", "-n", "1", head], repository)
        _, changed, _ = run_git(["diff-tree", "--no-commit-id", "--name-only", "-r", "-z", head], repository)
        paths = [p for p in changed.split("\x00") if p]
        if parents.split() != [head, remote_commit] or not paths or any(not p.startswith(relative + "/") for p in paths):
            raise ValueError("Archive branch contains unrelated unpublished commits or diverged; reconcile manually before publishing")
        if run_git(["diff", "--quiet", head, "--", relative], repository)[0] != 0 or run_git(["ls-files", "--others", "--exclude-standard", "--", relative], repository)[1]:
            raise ValueError("Snapshot changed since its local commit; do not publish")
        commit, outcome = head, "pushed"
    else:
        added, _, error = run_git(["add", "-A", "--", relative], repository)
        if added != 0:
            raise ValueError(f"cannot stage archive snapshot (check whether the repository ignores it): {error}")
        staged_code, _, staged_error = run_git(["diff", "--cached", "--quiet", "--", relative], repository)
        if staged_code not in (0, 1):
            raise ValueError(f"cannot inspect staged snapshot: {staged_error}")
        # Every manifest file must actually be staged; ignore rules must not produce a partial snapshot.
        _, tracked, _ = run_git(["ls-files", "-z", "--", relative], repository)
        expected = {f.relative_to(repository).as_posix() for f in safe_tree(target)}
        if set(tracked.split("\x00")) - {""} != expected:
            raise ValueError("Archive repository ignores some snapshot files; refusing partial snapshot")
        if staged_code == 0:
            return {"status": "already-published", "repository": str(repository), "snapshot": relative, "remote": chosen, "branch": branch, "commit": head}
        commit_note = message or f"archive: {Path(relative).parent.name} {Path(relative).name}"
        committed, stdout, error = run_git(["commit", "-q", "-m", commit_note, "--", relative], repository)
        if committed != 0:
            raise ValueError(f"cannot commit archive snapshot: {error or stdout}")
        commit = run_git(["rev-parse", "HEAD"], repository)[1]
        outcome = "pushed"
    # Revalidate the exact outgoing commit; push an immutable SHA, never mutable HEAD.
    _, parents, _ = run_git(["rev-list", "--parents", "-n", "1", commit], repository)
    _, changed, _ = run_git(["diff-tree", "--no-commit-id", "--name-only", "-r", "-z", commit], repository)
    paths = [p for p in changed.split("\x00") if p]
    if parents.split() != [commit, remote_commit] or not paths or any(not p.startswith(relative + "/") for p in paths):
        raise ValueError("Outgoing commit contains unrelated history or files; no push attempted")
    _, committed_files, _ = run_git(["ls-tree", "-r", "--name-only", "-z", commit, "--", relative], repository)
    if set(committed_files.split("\x00")) - {""} != {f.relative_to(repository).as_posix() for f in safe_tree(target)} or run_git(["diff", "--quiet", commit, "--", relative], repository)[0] != 0:
        raise ValueError("Outgoing snapshot is incomplete or differs from the validated files; no push attempted")
    pushed, _, push_error = run_git(["push", "-q", chosen, f"{commit}:refs/heads/{branch}"], repository)
    if pushed != 0:
        raise ValueError(f"Cannot push snapshot to {chosen}/{branch}; no automatic fetch/rebase: {push_error}")

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



# The remembered archive location lives next to this Skill in the *installed* copy
# (~/.config/opencode/skills/a-project-archive/archive_root.conf). It is user data:
# the installer never ships it, so reinstall/uninstall leave it alone.
#
# Two things are remembered, because a snapshot needs both:
#   repository   absolute path of the archive Git work tree (where commits happen)
#   snapshot_dir directory *inside* that repository that holds project snapshots
#                (e.g. "工程记录" for the personal knowledge base; "." for a
#                 repository dedicated to archives only)
#
# File format (JSON, written by --set-*):
#   {"repository": "<absolute path>", "snapshot_dir": "<relative path or .>"}
# A legacy plain-text file is still readable: it is treated as
#   {"repository": <that path>, "snapshot_dir": "."}
CONFIG_FILE = Path(__file__).resolve().parent.parent / "archive_root.conf"
EXIT_UNCONFIGURED = 3
DEFAULT_SNAPSHOT_DIR = "."


def clean_snapshot_dir(value: str) -> str:
    """Normalise a snapshot directory to a relative POSIX path, or '.' for the repository root."""
    text = str(value).replace("\\", "/").strip()
    if not text:
        return DEFAULT_SNAPSHOT_DIR
    candidate = Path(text)
    if candidate.is_absolute():
        raise ValueError(f"snapshot dir must be relative to the archive repository: {value}")
    parts = [part for part in candidate.parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError(f"snapshot dir must not leave the archive repository: {value}")
    return "/".join(parts) if parts else DEFAULT_SNAPSHOT_DIR


def work_tree_root(path: Path) -> Path | None:
    code, output, _ = run_git(["rev-parse", "--show-toplevel"], path)
    if code != 0 or not output:
        return None
    return Path(output).resolve()


def resolve_repository(path: Path) -> tuple[Path, str]:
    """Return (repository or plain directory, snapshot dir implied by `path`).

    Inside a Git work tree the path is canonicalised to the work-tree root and the
    remaining sub-path becomes the snapshot directory; passing .../工程记录 therefore
    records "snapshots live in 工程记录 of that repository". A directory that is not
    Git-managed is kept as-is, so the snapshot can still be created locally and the
    push step reports why it could not be published.
    """
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"archive location does not exist or is not a directory: {resolved}")
    top = work_tree_root(resolved)
    if top is None:
        return resolved, DEFAULT_SNAPSHOT_DIR
    relative = resolved.relative_to(top)
    return top, clean_snapshot_dir(relative.as_posix())


def snapshot_parent(repository: Path, snapshot_dir: str) -> Path:
    """Absolute directory that holds <project>/<timestamp> snapshots."""
    resolved = repository.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"archive repository does not exist or is not a directory: {resolved}")
    parent = (resolved / snapshot_dir).resolve()
    if not contains(resolved, parent):
        raise ValueError(f"snapshot dir leaves the archive repository: {snapshot_dir}")
    return parent


def load_config(config_file: Path | None = None) -> dict[str, object] | None:
    config_file = config_file or CONFIG_FILE
    try:
        text = config_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError(f"cannot parse {config_file}: {error}") from error
        repository = str(data.get("repository") or "").strip()
        if not repository:
            raise ValueError(f"{config_file} has no repository entry")
        return {
            "repository": Path(repository).expanduser(),
            "snapshot_dir": clean_snapshot_dir(str(data.get("snapshot_dir", DEFAULT_SNAPSHOT_DIR))),
        }
    return {"repository": Path(text).expanduser(), "snapshot_dir": DEFAULT_SNAPSHOT_DIR}


def save_config(repository: Path, snapshot_dir: str, config_file: Path | None = None) -> dict[str, object]:
    config_file = config_file or CONFIG_FILE
    resolved = repository.expanduser()
    if not resolved.is_absolute():
        raise ValueError(f"archive repository must be an absolute path: {repository}")
    resolved = resolved.resolve()
    if not resolved.is_dir():
        raise ValueError(f"archive repository does not exist or is not a directory: {resolved}")
    sub = clean_snapshot_dir(snapshot_dir)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"repository": str(resolved), "snapshot_dir": sub}
    config_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"repository": resolved, "snapshot_dir": sub}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, help="project to archive (required unless only setting the location)")
    parser.add_argument(
        "--archive-root",
        type=Path,
        help="one-off archive repository or snapshot directory; overrides the remembered setting without saving it",
    )
    parser.add_argument(
        "--snapshot-dir",
        metavar="REL",
        help="one-off snapshot directory inside the archive repository (overrides the remembered one)",
    )
    parser.add_argument(
        "--set-archive-root",
        type=Path,
        metavar="PATH",
        help="remember PATH as the archive repository, or as the snapshot directory inside it",
    )
    parser.add_argument(
        "--set-snapshot-dir",
        metavar="REL",
        help="remember REL as the snapshot directory inside the remembered archive repository",
    )
    parser.add_argument("--show-archive-root", action="store_true", help="print the remembered location and exit")
    parser.add_argument("--remote", default=None, help="Git remote to push to (default: origin, else the only remote)")
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="skip the mandatory publish step (destructive escape hatch; the snapshot then exists only on this machine)",
    )
    args = parser.parse_args()
    try:
        if args.show_archive_root:
            config = load_config()
            if config is None:
                print(json.dumps({"configured": False, "config": str(CONFIG_FILE)}, ensure_ascii=False))
                return EXIT_UNCONFIGURED
            repository = Path(config["repository"])
            sub = str(config["snapshot_dir"])
            print(
                json.dumps(
                    {
                        "configured": True,
                        "repository": str(repository),
                        "snapshot_dir": sub,
                        "snapshot_parent": str(snapshot_parent(repository, sub)),
                        "config": str(CONFIG_FILE),
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        if args.set_archive_root is not None or args.set_snapshot_dir is not None:
            if args.set_archive_root is not None:
                repository, implied = resolve_repository(args.set_archive_root)
                sub = args.set_snapshot_dir if args.set_snapshot_dir is not None else implied
            else:
                config = load_config()
                if config is None:
                    print(
                        "[!] No archive repository is configured. Pass --set-archive-root <path> first.",
                        file=sys.stderr,
                    )
                    return EXIT_UNCONFIGURED
                repository = Path(config["repository"])
                sub = str(args.set_snapshot_dir)
            saved = save_config(repository, sub)
            print(
                json.dumps(
                    {
                        "repository": str(saved["repository"]),
                        "snapshot_dir": str(saved["snapshot_dir"]),
                        "snapshot_parent": str(snapshot_parent(Path(saved["repository"]), str(saved["snapshot_dir"]))),
                        "config": str(CONFIG_FILE),
                    },
                    ensure_ascii=False,
                )
            )
            if args.project_root is None:
                return 0

        if args.project_root is None:
            parser.error("--project-root is required to archive")

        if args.archive_root is not None or args.snapshot_dir is not None:
            if args.archive_root is not None:
                repository, implied = resolve_repository(args.archive_root)
                sub = args.snapshot_dir if args.snapshot_dir is not None else implied
            else:
                config = load_config()
                if config is None:
                    raise ValueError("--snapshot-dir needs a remembered archive repository")
                repository = Path(config["repository"])
                sub = str(args.snapshot_dir)
        else:
            config = load_config()
            if config is None:
                print(
                    "[!] No archive root is configured and none was given. Ask the user for the archive "
                    "repository directory (or the snapshot directory inside it), then run again with "
                    f"--set-archive-root <path> (saved to {CONFIG_FILE}).",
                    file=sys.stderr,
                )
                return EXIT_UNCONFIGURED
            repository = Path(config["repository"])
            sub = str(config["snapshot_dir"])

        parent = snapshot_parent(repository, sub)
        parent.mkdir(parents=True, exist_ok=True)

        target = archive(args.project_root, parent)
        # Archiving is not finished until the snapshot is pushed: a local commit
        # does not survive the machine. Only an explicit --no-push skips this.
        report: dict[str, object] = {"status": "skipped", "reason": "--no-push"}
        if not args.no_push:
            report = push(target, args.remote)
    except (OSError, ValueError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1
    result = {
        "archive": str(target),
        "repository": str(repository),
        "snapshot_dir": sub,
        "archive_root": str(parent),
        "publish": report,
    }
    if not args.no_push and report.get("status") in {"not-a-repository", "no-remote", "detached-head"}:
        print(json.dumps(result, ensure_ascii=False))
        explanation = {
            "not-a-repository": f"the archive location is not a Git work tree, so the snapshot stays local: {target}",
            "no-remote": "the archive repository has no remote configured, so the snapshot stays local",
            "detached-head": "the archive repository is on a detached HEAD, so the snapshot cannot be published; check out a branch",
        }[str(report["status"])]
        print(
            f"[!] Archive created but NOT pushed: {explanation}. Make the archive repository a Git work tree with a "
            "remote (or pass --archive-root to one), then push the snapshot again.",
            file=sys.stderr,
        )
        return EXIT_PUSH_FAILED
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
