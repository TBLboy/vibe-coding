#!/usr/bin/env python3
"""Set context limits and input modalities for models of an OpenCode provider.

Edits only `provider.<id>.models.*.limit` and `.modalities`, drops the
deprecated `attachment` flag, and leaves every other key byte-identical.

Usage:
  configure_models.py --provider llmcenter
  configure_models.py --provider llmcenter --context 500000 --no-image
  configure_models.py --provider llmcenter --model gpt-6-sol --dry-run
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
from collections import OrderedDict
from pathlib import Path

DEFAULT_CONTEXT = 500_000
DEFAULT_OUTPUT = 32_000


def config_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    base = os.environ.get("OPENCODE_CONFIG_DIR")
    if base:
        return Path(base).expanduser() / "opencode.json"
    return Path.home() / ".config" / "opencode" / "opencode.json"


def load(path: Path) -> OrderedDict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=OrderedDict)


def atomic_write(path: Path, payload: OrderedDict) -> None:
    """Write via a temp file in the same directory, preserving permissions."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        mode = 0o600
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", required=True, help="provider id under `provider` in opencode.json")
    parser.add_argument("--config", help="path to opencode.json (default: $OPENCODE_CONFIG_DIR or ~/.config/opencode)")
    parser.add_argument("--model", action="append", default=[], help="limit to this model id (repeatable)")
    parser.add_argument("--context", type=int, default=DEFAULT_CONTEXT, help=f"context window (default: {DEFAULT_CONTEXT})")
    parser.add_argument("--output", type=int, default=DEFAULT_OUTPUT, help=f"max output tokens (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--no-image", action="store_true", help="declare text-only input instead of text+image")
    parser.add_argument("--keep-limit", action="store_true", help="do not touch `limit`")
    parser.add_argument("--keep-modalities", action="store_true", help="do not touch `modalities`")
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing")
    parser.add_argument("--backup", action="store_true", help="keep a timestamped backup (WARNING: contains the API key)")
    args = parser.parse_args()

    path = config_path(args.config)
    if not path.is_file():
        print(f"error: config not found: {path}", file=sys.stderr)
        return 2

    cfg = load(path)
    providers = cfg.get("provider")
    if not isinstance(providers, dict) or args.provider not in providers:
        available = sorted(providers) if isinstance(providers, dict) else []
        print(f"error: provider {args.provider!r} not found; available: {available}", file=sys.stderr)
        return 2
    models = providers[args.provider].get("models")
    if not isinstance(models, dict) or not models:
        print(f"error: provider {args.provider!r} declares no `models`", file=sys.stderr)
        return 2

    if args.model:
        unknown = [m for m in args.model if m not in models]
        if unknown:
            print(f"error: unknown model(s) {unknown}; available: {sorted(models)}", file=sys.stderr)
            return 2
        targets = args.model
    else:
        targets = list(models)

    before = copy.deepcopy(cfg)
    modality_input = ["text"] if args.no_image else ["text", "image"]
    rows: list[tuple[str, str, str]] = []

    for name in targets:
        entry = models[name]
        if not isinstance(entry, dict):
            print(f"error: model {name!r} is not an object", file=sys.stderr)
            return 2
        notes: list[str] = []

        if not args.keep_limit:
            old = entry.get("limit")
            new = OrderedDict([("context", args.context), ("output", args.output)])
            if old != new:
                notes.append(f"limit {old or 'default'} -> {dict(new)}")
            entry["limit"] = new

        if not args.keep_modalities:
            old_in = (entry.get("modalities") or {}).get("input")
            entry["modalities"] = OrderedDict([("input", list(modality_input)), ("output", ["text"])])
            if old_in != modality_input:
                notes.append(f"input {old_in or 'default'} -> {modality_input}")

        if entry.pop("attachment", None) is not None:
            notes.append("removed deprecated `attachment`")

        models[name] = OrderedDict(sorted(entry.items()))
        rows.append((name, "CHANGED" if notes else "ok", "; ".join(notes)))

    width = max(len(r[0]) for r in rows)
    for name, state, notes in rows:
        print(f"{name:<{width}}  {state:<7}  {notes}")
    changed = [r for r in rows if r[1] == "CHANGED"]
    print(f"\n{len(changed)}/{len(rows)} model(s) changed in provider {args.provider!r}")

    if args.dry_run:
        print("dry-run: no file written")
        return 0
    if not changed:
        print("nothing to write")
        return 0

    # Guard: nothing outside limit/modalities/attachment may differ.
    after = copy.deepcopy(cfg)
    for snapshot in (before, after):
        for entry in snapshot["provider"][args.provider]["models"].values():
            if isinstance(entry, dict):
                for key in ("limit", "modalities", "attachment"):
                    entry.pop(key, None)
    if before != after:
        print("error: refusing to write, unrelated keys changed", file=sys.stderr)
        return 1

    if args.backup:
        stamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.name}.bak-{stamp}")
        shutil.copy2(path, backup)
        os.chmod(backup, 0o600)
        print(f"backup: {backup}")
        print("WARNING: the backup holds your API key in plain text; delete it once verified.")

    atomic_write(path, cfg)
    print(f"wrote: {path}")
    print("verify with: opencode api --standalone get /api/model")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
