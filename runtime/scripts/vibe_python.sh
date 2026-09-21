vibe_check_interpreter() {
  local candidate="$1"
  case "$candidate" in /*|[A-Za-z]:[\\/]*) ;; *) return 1 ;; esac
  [[ -f "$candidate" ]] && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 3)' >/dev/null 2>&1
}

vibe_resolve_python() {
  local config_home="$1" mode="${2:-runtime}" candidate="${VIBE_PYTHON:-}" manager directory depth name
  local config_file="$config_home/vibe-python"
  if [[ -z "$candidate" && -f "$config_file" ]]; then
    candidate="$(<"$config_file")"
    candidate="${candidate#$'\xef\xbb\xbf'}"
    candidate="${candidate%$'\r'}"
    if [[ -z "$candidate" || "$candidate" == *$'\n'* || "$candidate" == *$'\r'* ]]; then
      printf 'Invalid interpreter configuration: %s\n' "$config_file" >&2
      return 2
    fi
  fi
  if [[ -n "$candidate" ]]; then
    if ! vibe_check_interpreter "$candidate"; then
      printf 'Configured Vibe Python must be an absolute executable path to Python 3.11+: %s\n' "$candidate" >&2
      return 2
    fi
    printf '%s\n' "$candidate"
    return
  fi
  if [[ "$mode" != bootstrap ]]; then
    printf 'Missing %s. Install Vibe or configure VIBE_PYTHON; runtime commands never create environments.\n' "$config_file" >&2
    return 2
  fi
  if [[ -n "${VIBE_BOOTSTRAP_PYTHON:-}" ]]; then
    if ! vibe_check_interpreter "$VIBE_BOOTSTRAP_PYTHON"; then
      printf 'VIBE_BOOTSTRAP_PYTHON must be an absolute executable path to Python 3.11+.\n' >&2
      return 2
    fi
    printf '%s\n' "$VIBE_BOOTSTRAP_PYTHON"
    return
  fi
  local candidates=("${CONDA_PYTHON_EXE:-}")
  manager="${CONDA_EXE:-$(command -v conda || true)}"
  if [[ -n "$manager" ]]; then
    directory="$(dirname -- "$manager")"
    for depth in 1 2 3; do
      candidates+=("$directory/python" "$directory/python.exe")
      directory="$(dirname -- "$directory")"
    done
  fi
  for name in miniforge3 mambaforge miniconda3 anaconda3; do
    candidates+=("$HOME/$name/bin/python" "$HOME/$name/python.exe")
  done
  candidates+=("$(command -v python3 || true)" "$(command -v python || true)")
  for candidate in "${candidates[@]}"; do
    if [[ -n "$candidate" ]] && vibe_check_interpreter "$candidate"; then
      printf '%s\n' "$candidate"
      return
    fi
  done
  printf 'Cannot bootstrap Vibe. Install Conda and set VIBE_BOOTSTRAP_PYTHON to its absolute Python 3.11+ executable.\n' >&2
  return 2
}
