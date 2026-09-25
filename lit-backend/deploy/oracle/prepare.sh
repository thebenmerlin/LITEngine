#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
backend_dir="$(cd "$script_dir/../.." && pwd)"

mkdir -p "$script_dir/state"
if [[ ! -f "$script_dir/.env.stage" ]]; then
  cp "$script_dir/.env.stage.example" "$script_dir/.env.stage"
  chmod 600 "$script_dir/.env.stage"
  echo "Created $script_dir/.env.stage; set ALLOWED_ORIGINS and optional HUGGINGFACE_API_KEY."
fi
if [[ ! -f "$script_dir/state/precedent_index.json" ]]; then
  cp "$backend_dir/fixtures/precedent_index.json" "$script_dir/state/precedent_index.json"
  echo "Copied the 3-document fixture index for staging smoke checks. Replace it with a dated corpus before public use."
fi

python3 - "$script_dir/state/precedent_index.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
metadata = data.get("metadata", [])
if not metadata or any(not item.get("date") for item in metadata):
    raise SystemExit("Precedent index must contain dated entries")
print(f"Index ready: {len({item['doc_id'] for item in metadata})} documents, {len(metadata)} vectors")
PY
