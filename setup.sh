#!/bin/sh
# One-time setup. Run from the kit folder: sh setup.sh   (Windows: Git Bash)
set -e
cd "$(dirname "$0")"
PY=$(command -v python || command -v python3 || command -v py || true)
[ -n "$PY" ] || { echo "Install Python 3.9+ and put it on PATH, then re-run."; exit 1; }
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 9))' || { echo "Python 3.9+ needed."; exit 1; }
[ -d .git ] || git init -q
git config core.hooksPath tools/hooks
chmod +x tools/hooks/pre-commit 2>/dev/null || true
for f in LEARNINGS.md decisions.md; do [ -f "$f" ] || printf '# %s\n' "${f%.md}" > "$f"; done
grep -q '^## Outcomes' decisions.md || printf '\n## Outcomes\n' >> decisions.md
if [ -z "$(git config user.email)" ]; then
  echo "Set your git identity first, then re-run:"
  echo '  git config --global user.name "Your Name"'
  echo '  git config --global user.email "you@example.com"'
  exit 1
fi
git add -A && git commit -qm "brain: initial setup" && echo "Done. Open this folder in Claude Code and fill in MEMORY.md."
