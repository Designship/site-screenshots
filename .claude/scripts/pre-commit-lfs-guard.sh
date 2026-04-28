#!/usr/bin/env bash
# 1MB 以上のファイルが LFS を経由せず通常 git に乗ろうとしたら止める。
# 各リポで `cp .claude/scripts/pre-commit-lfs-guard.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit`
# を 1 度実行しておく(install_hooks.sh で自動化)。

set -euo pipefail

THRESHOLD=$((1024 * 1024))   # 1 MB
violations=0

# git lfs が知っているファイルのリスト
lfs_files=$(git lfs ls-files -n 2>/dev/null || true)

while IFS= read -r path; do
  [ -f "$path" ] || continue
  size=$(wc -c < "$path" | tr -d ' ')
  if [ "$size" -gt "$THRESHOLD" ]; then
    if ! grep -Fxq "$path" <<<"$lfs_files"; then
      echo "✗ $path ($((size/1024)) KB) は 1MB 超ですが LFS に track されていません" >&2
      echo "   解決: git lfs track \"$path\" && git add .gitattributes \"$path\"" >&2
      violations=$((violations + 1))
    fi
  fi
done < <(git diff --cached --name-only --diff-filter=AM)

if [ "$violations" -gt 0 ]; then
  echo "" >&2
  echo "$violations 件の LFS 違反があるため commit を中止しました。" >&2
  exit 1
fi
