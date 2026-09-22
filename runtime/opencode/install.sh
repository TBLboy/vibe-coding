#!/usr/bin/env bash
# Entry point for the Vibe Coding OpenCode client surface.
#
# Usage:
#   ./runtime/opencode/install.sh [install|update|verify|preflight|uninstall] [options]
#
# With no action it defaults to `install`. All options are forwarded to
# scripts/opencode_installer.py (--opencode-home, --skip-preflight,
# --skip-plugin-install).
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"

python_candidates=()
if [[ -n "${VIBE_PYTHON:-}" ]]; then
  python_candidates+=("$VIBE_PYTHON")
fi
for config_home in "${OPENCODE_CONFIG_DIR:-}" "${CODEX_HOME:-$HOME/.codex}" "$HOME/.codex"; do
  if [[ -n "$config_home" && -f "$config_home/vibe-python" ]]; then
    python_candidates+=("$(<"$config_home/vibe-python")")
  fi
done
python_candidates+=(python3 python)

python_bin=""
for candidate in "${python_candidates[@]}"; do
  [[ -n "$candidate" ]] || continue
  resolved="$(command -v -- "$candidate" 2>/dev/null || true)"
  [[ -n "$resolved" ]] || continue
  if "$resolved" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    python_bin="$resolved"
    break
  fi
done

if [[ -z "$python_bin" ]]; then
  printf '%s\n' 'Python 3.11+ is required for the Vibe runtime.' >&2
  printf '%s\n' 'Set VIBE_PYTHON, or install Python 3.11+, or run scripts/bootstrap_vibe_python.py first.' >&2
  exit 2
fi

if [[ $# -eq 0 ]]; then
  set -- install
elif [[ "$1" == -* ]]; then
  # Options were given without an explicit action: default to `install`.
  set -- install "$@"
fi

export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
exec "$python_bin" "$root/scripts/opencode_installer.py" "$@"
