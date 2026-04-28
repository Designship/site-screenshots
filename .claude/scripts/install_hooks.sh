#!/usr/bin/env bash
# このリポの .git/hooks/ に pre-commit を仕込む。
# 初回 clone 直後に 1 回だけ実行する。
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
SRC="$ROOT/.claude/scripts/pre-commit-lfs-guard.sh"
DST="$ROOT/.git/hooks/pre-commit"
cp "$SRC" "$DST"
chmod +x "$DST"
echo "installed: $DST"
