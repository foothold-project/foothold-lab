#!/usr/bin/env bash
# The launcher ex42_eval_once --next-stage-launcher points at (absolute path, executable). It reads EX42_AUTO_* from
# the environment, sources the machine profile, sends the one-line notice and exec's the trainer (see the .py).
# Extra arguments go to the python module: --print (show the command) or --dry-run (CPU first-update check).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
profile="${FOOTHOLD_LINUX_ENV:-$HOME/mai/foothold-linux.env}"
if [[ ! -f "$profile" ]]; then
    echo "Linux machine profile not found: $profile" >&2
    exit 2
fi
set -a
# shellcheck disable=SC1090
source "$profile"
set +a
: "${ISAAC311_PYTHON:?ISAAC311_PYTHON is required}"
export PYTHONPATH="$(cd "$here/../.." && pwd)${PYTHONPATH:+:$PYTHONPATH}"
exec "$ISAAC311_PYTHON" "$here/ex42_stage_launcher.py" "$@"
