#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"

./prepare.sh
docker_cmd=(docker)
if ! docker info >/dev/null 2>&1; then
  docker_cmd=(sudo docker)
fi
"${docker_cmd[@]}" compose -f compose.yaml config --quiet
"${docker_cmd[@]}" compose -f compose.yaml up -d --build
python3 smoke.py --base-url http://127.0.0.1:8000 --wait-seconds 240
