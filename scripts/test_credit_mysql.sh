#!/usr/bin/env bash
# Isolated MySQL 8.4 test server. No host port and no live database connection.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LMS_CONTAINER="${CBA_TEST_LMS_CONTAINER:-tutor_local-lms-1}"
TEST_CONTAINER="cba-credit-mysql-test-$(date -u +%Y%m%dT%H%M%SZ)-$$"
REVIEW_PATH="/tmp/${TEST_CONTAINER}-source"
SECRET_FILE="$(mktemp)"
chmod 600 "$SECRET_FILE"
OWNED_CONTAINER=""
cleanup() {
  if [ -n "$OWNED_CONTAINER" ]; then docker rm -fv "$OWNED_CONTAINER" >/dev/null 2>&1 || true; fi
  rm -f "$SECRET_FILE"
}
trap cleanup EXIT
docker exec "$LMS_CONTAINER" python -c '
import socket
s=socket.socket(); s.settimeout(1)
try:
    s.connect(("127.0.0.1",3307))
except OSError:
    pass
else:
    raise SystemExit("Stopped: test port 3307 is occupied.")
finally:
    s.close()
'
python - "$SECRET_FILE" <<'PY'
import secrets, sys
from pathlib import Path
Path(sys.argv[1]).write_text(
    "MYSQL_ROOT_PASSWORD=" + secrets.token_hex(32) + "\n"
    "MYSQL_ROOT_HOST=%\nMYSQL_DATABASE=cba_credit_test_base\n"
)
PY
OWNED_CONTAINER="$(docker create --name "$TEST_CONTAINER" \
  --network "container:$LMS_CONTAINER" \
  --memory 1g --cpus 1 --env-file "$SECRET_FILE" \
  --mount type=volume,destination=/var/lib/mysql \
  mysql:8.4.11 --port=3307 --bind-address=127.0.0.1 --mysqlx=OFF \
  --innodb-buffer-pool-size=128M --max-connections=30)"
docker start "$OWNED_CONTAINER" >/dev/null
READY=0
for attempt in $(seq 1 60); do
  if docker exec "$TEST_CONTAINER" sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqladmin --protocol=tcp -h127.0.0.1 -P3307 -uroot ping --silent' >/dev/null 2>&1; then
    READY=1; break
  fi
  sleep 2
done
if [ "$READY" != 1 ]; then
  printf '%s\n' "Isolated MySQL did not become ready." >&2
  exit 1
fi
docker cp "$REPO_ROOT" "$LMS_CONTAINER:$REVIEW_PATH" >/dev/null
docker exec -i --env-file "$SECRET_FILE" -e PYTHONPATH="$REVIEW_PATH" \
  -w /openedx/edx-platform "$LMS_CONTAINER" python <<'PY'
import os
from django.conf import settings
settings.configure(
    SECRET_KEY="isolated-mysql-credit-tests-only",
    INSTALLED_APPS=[
        "django.contrib.auth", "django.contrib.contenttypes",
        "cba_production.learning_credits.apps.LearningCreditsConfig",
    ],
    DATABASES={"default": {
        "ENGINE": "django.db.backends.mysql", "NAME": "cba_credit_test_base",
        "HOST": "127.0.0.1", "PORT": "3307", "USER": "root",
        "PASSWORD": os.environ["MYSQL_ROOT_PASSWORD"],
        "TEST": {"NAME": "test_cba_credit_isolated"},
        "OPTIONS": {"charset": "utf8mb4"},
    }},
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField", USE_TZ=True,
)
import django
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT @@port, DATABASE(), VERSION()")
    port, name, server_version = cursor.fetchone()
    assert int(port) == 3307 and name == "cba_credit_test_base"
    print("Isolated test server:", server_version, "port", port)
from django.core.management import call_command
call_command("test", "cba_production.learning_credits.tests", verbosity=2, interactive=False)
PY
