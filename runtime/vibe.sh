#!/usr/bin/env bash
set -euo pipefail
runtime="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$runtime/scripts/vibe_python.sh"
# Resolve the config home. An explicit environment variable wins; otherwise infer it
# from where this wrapper is installed — the installer places it at
# <config-home>/vibe-workflow/vibe.sh, so the parent directory holds vibe-python.
# A source-tree checkout has no vibe-python beside it, so it falls back to the
# OpenCode default. There is deliberately no ~/.codex fallback: after the codex
# delivery face was removed that path can point at an interpreter that no longer
# has the Vibe requirements, and silently using it is worse than failing.
if [[ -n "${OPENCODE_CONFIG_DIR:-}" ]]; then
  config_home="$OPENCODE_CONFIG_DIR"
elif [[ -f "$runtime/../vibe-python" ]]; then
  config_home="$(cd -- "$runtime/.." && pwd)"
else
  config_home="$HOME/.config/opencode"
fi
forward=()
while (( $# )); do
  case "$1" in
    --config-home)
      if (( $# < 2 )) || [[ -z "$2" ]]; then printf '%s\n' '--config-home requires a path.' >&2; exit 2; fi
      config_home="$2"; shift 2 ;;
    --config-home=*)
      config_home="${1#--config-home=}"
      if [[ -z "$config_home" ]]; then printf '%s\n' '--config-home requires a path.' >&2; exit 2; fi
      shift ;;
    *) forward+=("$1"); shift ;;
  esac
done
python_bin="$(vibe_resolve_python "$config_home")"
export OPENCODE_CONFIG_DIR="$config_home" PYTHONUTF8=1 PYTHONIOENCODING=utf-8
exec "$python_bin" -B "$runtime/scripts/vibe.py" "${forward[@]}"
