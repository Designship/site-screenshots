# このリポジトリで Claude Code が守るルール

このファイルは、Claude Code(AI コーディング補助)が作業を始める前に**必ず読むルールブック**です。
書かれている内容はそのまま Claude の行動指針になります。

---

## 1. 言葉づかい

- **必ず日本語で答える**(コマンドやファイル名・コードはそのまま英語で OK)
- 専門用語は初めて出てくるときに「(=何々のこと)」のように一言補足する
- ステップごとに何をやっているかを 1〜2 文で報告する(黙々と進めない)
- 報告は短く具体的に。長い段落より箇条書きが望ましい

## 2. ブランチと PR のルール

- **`main` に直接 commit / push しない**。必ず別ブランチで作業する
- ブランチ作業は **git worktree**(=同じリポを別フォルダに展開して並行作業できる仕組み)で行う:
  ```bash
  git worktree add ../.worktrees/<このリポ名>/<branch名> -b <branch名>
  cd ../.worktrees/<このリポ名>/<branch名>
  ```
  作業フォルダは `<リポの親フォルダ>/.worktrees/<リポ名>/<branch名>` に作る
- 作業が終わったら **PR を作る**:
  ```bash
  gh pr create --draft --title "..." --body "..."
  ```
- 完成していないものは Draft、完成したら Ready for review に切り替える

## 3. PR を作る前に **必ず**スクショを取る

PR 作成の直前または直後に、以下を実行する:

```bash
.claude/scripts/screenshot_diff.py <PR番号>
```

このスクリプトは:

1. `git diff main...HEAD --name-only` で**変更があったページだけ**を判定する
2. `main`(現状の本番)と PR ブランチの両方を、別ポートでローカル起動する
3. それぞれを mobile (375px) / desktop (1280px) で full-page スクショ撮影する
4. `Designship/site-screenshots` リポにディレクトリを作って push する
5. `raw.githubusercontent.com/...` の URL を組み立て、PR にコメントとして投稿する

**理由**: GitHub には画像を API で直接コメントに貼る公式手段がない(検証済み)ので、専用リポ + raw URL という回り道を取っている。詳しくは `.claude/skills/pr-screenshot-diff/SKILL.md` 参照。

## 4. Git LFS のルール

- **1 MB 以上のファイル**(画像・動画・大きなフォント等)は LFS で扱う
- `.gitattributes` で拡張子ベースの track が設定済み(`*.png`, `*.jpg`, `*.webp`, `*.mp4`, `*.woff2` など)
- 拡張子なしファイル(Studio の UUID 名画像など)を新たに add するときは、**サイズが 1 MB 以上なら手動で track**:
  ```bash
  git lfs track <ファイルへのパス>
  ```
- pre-commit hook が 1 MB 超のファイルを通常 git で commit しようとしたら止める設定になっている(`.git/hooks/pre-commit`)

## 5. やってはいけないこと

- `git push --force` / `git reset --hard` / `git push --no-verify` を**勝手に**実行しない。必ずユーザーに確認する
- main の上で `git commit` を実行しない
- LFS 設定を回避しようとしない(コミット時に hook が止めたら、ファイルを LFS に track してから再度 commit)
- スクショ取得スクリプトをスキップして PR を作らない

## 6. ローカルでの動作確認

各リポは静的サイト(HTML + CSS + 画像のみ)。動作確認は:

```bash
python3 -m http.server <ポート番号>
```

主要ポート割り当て:

| リポ | ポート(main) | ポート(worktree) |
|---|---|---|
| site-corporate  | 8080 | 9080 |
| site-conference | 8081 | 9081 |
| site-do         | 8082 | 9082 |
| site-dialogue   | 8083 | 9083 |
| site-studio     | 8084 | 9084 |

スクショ取得スクリプトはこの規約に従って 2 つ起動する。

## 7. 関連リソース

- スクショ保管庫: <https://github.com/Designship/site-screenshots>
- 共通の運用方針: 各 site-* リポの `.claude/` は基本的に**同一の内容**を保つ。改善するときは 5 リポすべてに反映する。
