# site-screenshots

`Designship/site-*` 各リポジトリで PR を作るときに自動撮影される **before / after スクリーンショット**の保管庫です。

## どう使われているか

1. `site-conference` などで PR を作るとき、Claude Code が `pr-screenshot-diff` skill を実行
2. 変更があったページを判定して、`main` の状態と PR ブランチの状態を Playwright で full-page スクショ
3. このリポにディレクトリを作って push → `raw.githubusercontent.com` の URL を取得
4. 元の PR にコメントとして画像が貼られる(GitHub の画像直貼り API は存在しないため、この方法を採用)

## ディレクトリ構造

```
<site-name>/pr-<番号>/
├── before/
│   ├── mobile_<page-slug>.png
│   └── desktop_<page-slug>.png
└── after/
    ├── mobile_<page-slug>.png
    └── desktop_<page-slug>.png
```

例: `site-conference/pr-42/before/desktop_2025_contents_session.png`

## 自動クリーンアップ

`.github/workflows/cleanup.yml` が **毎日 02:00 UTC**(日本時間 11:00)に走り、
親リポ側で **クローズ済み or マージ済みの PR** に対応するディレクトリを削除します。
ここに溜まり続けることはありません。

手動で全部消したいときは:

```bash
# このリポをクローンして
cd site-screenshots
rm -rf site-*/pr-*
git add -A && git commit -m "manual cleanup" && git push
```

## 注意

- **このリポは public** です(raw URL を匿名で見せるため)。機密情報を含むスクショを置かないでください。
- スクショは LFS ではなく**通常の git** に乗せています(PR ごとに数 MB、cleanup が回るのでリポは肥大化しません)。
- スクショ取得スクリプトは各 site-* リポの `.claude/scripts/screenshot_diff.py` にあります。
