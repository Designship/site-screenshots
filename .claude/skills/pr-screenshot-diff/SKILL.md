---
name: pr-screenshot-diff
description: 変更ページの before / after スクショを取り、site-screenshots に push、PR にコメントとして貼り付ける。PR を作る/更新するときに必ず使う。
---

# pr-screenshot-diff

## いつ使うか

`gh pr create` または `gh pr edit` で PR を作成・更新する**直前または直後**に、必ず実行する。

## 何をするか

1. `git merge-base main HEAD` でブランチ分岐点を特定
2. 分岐点から HEAD までの差分(`git diff --name-only`)を見て、変更があった HTML / 画像 / CSS の**ページ単位**を推定
3. `git worktree` を使って `main` の状態を `../.worktrees/<repo>/.shot-baseline` に展開
4. `python3 -m http.server` を 2 つ(main 用と現ブランチ用)別ポートで起動
5. Playwright (Chromium) で各ページを mobile (375px) / desktop (1280px) full-page でスクショ
6. `Designship/site-screenshots` をクローン(or pull)して `<site-name>/pr-<番号>/{before,after}/` に保存
7. push して raw URL を組み立て、`gh pr comment <PR番号> --body "..."` で PR に投稿

詳しい実装は `.claude/scripts/screenshot_diff.py` を読むこと。

## 引数と使い方

```bash
python3 .claude/scripts/screenshot_diff.py <PR番号>
# 例: python3 .claude/scripts/screenshot_diff.py 42
```

## 失敗時の対処

- 変更ページが 0 件 → 「ドキュメントだけの変更らしい」とユーザーに報告してスクショは省略
- ローカルサーバの起動に失敗 → ポートが既に使われていないか確認(`lsof -i :8081` 等)
- site-screenshots への push が rate limit に当たる → 数分待って再実行

## 認可

このスクリプトは `gh` CLI の認証を使う。Claude Code は新たな認証情報を要求しない。
ユーザー個人の login に依存しないよう、Designship 組織内でアクセスできる token を使うこと。
