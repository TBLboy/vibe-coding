#!/usr/bin/env bash
set -euo pipefail
runtime="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$runtime/scripts/vibe_python.sh"
# Resolve the config home. An explicit --config-home or OPENCODE_CONFIG_DIR wins;
# otherwise infer it from where this wrapper is installed — the installer places it at
# <config-home>/vibe-workflow/vibe.sh, so the parent directory holds vibe-python.
# A source-tree checkout has no vibe-python beside it, so it falls back to the OpenCode
# default. There is deliberately no ~/.codex fallback: after the codex delivery face was
# removed that path can point at an interpreter that no longer has the Vibe
# requirements, and silently using it is worse than failing.
#
# The home-directory fallback is resolved *after* the flags, and guarded, because this
# script runs under `set -u`: a stripped environment (a sandbox, a systemd unit, a CI
# runner) has no HOME, and `"$HOME/..."` would abort with "HOME: unbound variable"
# even when the caller passed an explicit --config-home that makes HOME irrelevant.
config_home="${OPENCODE_CONFIG_DIR:-}"
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
if [[ -z "$config_home" ]]; then
  if [[ -f "$runtime/../vibe-python" ]]; then
    config_home="$(cd -- "$runtime/.." && pwd)"
  elif [[ -n "${HOME:-}" ]]; then
    config_home="$HOME/.config/opencode"
  else
    printf '%s\n' 'Cannot resolve the OpenCode config directory: HOME is unset.' >&2
    printf '%s\n' 'Pass --config-home <dir> or set OPENCODE_CONFIG_DIR.' >&2
    exit 2
  fi
fi
python_bin="$(vibe_resolve_python "$config_home")"
export OPENCODE_CONFIG_DIR="$config_home" PYTHONUTF8=1 PYTHONIOENCODING=utf-8
exec "$python_bin" -B "$runtime/scripts/vibe.py" "${forward[@]}"
