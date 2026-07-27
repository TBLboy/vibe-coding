#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
config_home="${CODEX_HOME:-$HOME/.codex}"
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  if [[ "${args[$i]}" == "--codex-home" && $((i + 1)) -lt ${#args[@]} ]]; then
    config_home="${args[$((i + 1))]}"
  elif [[ "${args[$i]}" == --codex-home=* ]]; then
    config_home="${args[$i]#--codex-home=}"
  fi
done
bootstrap_python="${VIBE_BOOTSTRAP_PYTHON:-python3}"
python_bin="$("$bootstrap_python" "$root/scripts/bootstrap_vibe_python.py" \
  --codex-home "$config_home" \
  --requirements "$root/runtime/scripts/requirements.txt" \
  --env-name "${VIBE_CONDA_ENV:-vibe-coding}" \
  --print-python)"
exec "$python_bin" "$root/scripts/global_installer.py" update "$@"
