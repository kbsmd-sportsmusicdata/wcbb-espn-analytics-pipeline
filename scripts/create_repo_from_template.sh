#!/usr/bin/env bash
set -euo pipefail
OWNER='kbsmd-sportsmusicdata'
TEMPLATE='kbsmd-sportsmusicdata/template-sports-analytics'
REPO="${1:-wcbb-espn-analytics-pipeline}"
OVERLAY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v gh >/dev/null || { echo 'GitHub CLI missing. On Mac: brew install gh' >&2; exit 1; }
gh auth status >/dev/null || { echo 'Run: gh auth login' >&2; exit 1; }
if gh repo view "${OWNER}/${REPO}" >/dev/null 2>&1; then
  echo "Repository ${OWNER}/${REPO} already exists. No changes made." >&2
  exit 1
fi
gh repo create "${OWNER}/${REPO}" --template "${TEMPLATE}" --private --clone
DEST="$(pwd)/${REPO}"
# Import project-specific files OVER the generated template, leaving its other files intact.
cp -R "${OVERLAY}/." "${DEST}/"
cd "${DEST}"
git add .
git commit -m 'feat: install ESPN WCBB ingest, QA, DuckDB and scheduled Actions'
git push origin HEAD
printf '\nRepository created: https://github.com/%s/%s\n' "${OWNER}" "${REPO}"
printf 'Next: Actions -> ESPN Analytics WCBB — validated refresh -> Run workflow.\n'
