#!/usr/bin/env bash
set -euo pipefail

CBA_TUTOR_ROOT="$(tutor config printroot)"
export CBA_MFE_DOCKERFILE="$CBA_TUTOR_ROOT/env/plugins/mfe/build/mfe/Dockerfile"

python - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["CBA_MFE_DOCKERFILE"])
source = path.read_text()
old = "    python g++"
new = "    python3 g++"

if "ARG NODE_IMAGE=" not in source:
    raise SystemExit("Stopped: expected NODE_IMAGE build argument is missing.")

if source.count(old) == 1:
    backup = path.with_name("Dockerfile.before-python3")
    if not backup.exists():
        backup.write_text(source)
    path.write_text(source.replace(old, new, 1))
    print("Updated build dependency: python -> python3")
elif source.count(new) == 1:
    print("Python 3 build dependency already configured.")
else:
    raise SystemExit("Stopped: unexpected Python dependency declaration.")
PY

tutor images build mfe \
  --build-arg NODE_IMAGE=docker.io/node:24.14.1-bookworm-slim
