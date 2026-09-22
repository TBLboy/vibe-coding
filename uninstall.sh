#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
config_home="${CODEX_HOME:-$HOME/.codex}"
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  if [[ "${args[$i]}" == "--codex-home" ]]; then
    if (( i + 1 >= ${#args[@]} )) || [[ -z "${args[$((i + 1))]}" || "${args[$((i + 1))]}" == --* ]]; then
      printf '%s\n' '--codex-home requires a path.' >&2; exit 2
    fi
    config_home="${args[$((i + 1))]}"
  elif [[ "${args[$i]}" == --codex-home=* ]]; then
    config_home="${args[$i]#--codex-home=}"
  fi
done
if [[ -z "$config_home" ]]; then printf '%s\n' '--codex-home requires a path.' >&2; exit 2; fi
source "$root/runtime/scripts/vibe_python.sh"
bootstrap_python="$(vibe_resolve_python "$config_home" bootstrap)"
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
python_bin="$("$bootstrap_python" "$root/scripts/bootstrap_vibe_python.py" \
  --codex-home "$config_home" \
  --requirements "$root/runtime/scripts/requirements.txt" \
  --env-name "${VIBE_CONDA_ENV:-vibe-coding}" \
  --no-create \
  --print-python)"
exec "$python_bin" "$root/scripts/global_installer.py" uninstall "$@"
