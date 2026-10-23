#!/usr/bin/env bash
# Apply the reviewed source patches only. Does not deploy or import live courses.
set -euo pipefail
PATCH_DIR="$(cd "${1:-$(dirname "$0")}" && pwd)"
CBA_REPO="${CBA_CREDIT_REPO:-$HOME/src/cba-learning-credits}"
CATALOG_REPO="${CBA_CATALOG_REPO:-$HOME/src/catalog-extensions}"

check_repo() {
  local repo="$1" branch="$2" base="$3" patch="$4"
  git -C "$repo" rev-parse --show-toplevel >/dev/null
  if [ "$(git -C "$repo" branch --show-current)" != "$branch" ]; then
    printf '%s\n' "Stopped: $repo must be on $branch." >&2
    exit 1
  fi
  if [ -n "$(git -C "$repo" status --porcelain)" ]; then
    printf '%s\n' "Stopped: $repo has uncommitted or untracked files. Preserve and review them first." >&2
    exit 1
  fi
  if ! git -C "$repo" merge-base --is-ancestor "$base" HEAD; then
    printf '%s\n' "Stopped: $repo needs the current GitHub feature branch through $base." >&2
    exit 1
  fi
  git -C "$repo" apply --check "$patch"
}

(cd "$PATCH_DIR" && sha256sum --check SHA256SUMS)
check_repo "$CBA_REPO" feature/learning-credits e8bcb4b "$PATCH_DIR/studio-controls.patch"
check_repo "$CATALOG_REPO" fix/catalog-orgcode-contract 9cae5c2 "$PATCH_DIR/catalog-credit-fields.patch"
git -C "$CBA_REPO" am "$PATCH_DIR/studio-controls.patch"
git -C "$CATALOG_REPO" am "$PATCH_DIR/catalog-credit-fields.patch"
printf '\n%s\n' 'Both patches committed locally. No containers restarted, databases migrated, or courses imported.'
printf '%s\n' "Next: bash $CBA_REPO/scripts/verify_credit_review.sh"
printf '%s\n' 'After successful checks, push both feature branches to GitHub before deployment.'
