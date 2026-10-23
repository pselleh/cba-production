#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$REPO_ROOT/scripts/test_credit_mysql.sh"
printf '\n%s\n' 'CURRENT CMS RUNTIME (read-only)'
docker exec -i -w /openedx/edx-platform tutor_local-cms-1 \
  python manage.py cms shell < "$REPO_ROOT/scripts/check_credit_runtime.py"
printf '\n%s\n' 'CURRENT LMS RUNTIME (read-only)'
docker exec -i -w /openedx/edx-platform tutor_local-lms-1 \
  python manage.py lms shell < "$REPO_ROOT/scripts/check_credit_runtime.py"
printf '\n%s\n' 'TUTOR SOURCE MOUNTS (read-only)'
tutor mounts list
