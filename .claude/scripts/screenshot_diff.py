#!/usr/bin/env python3
"""
screenshot_diff.py <PR番号>

PR で変更があったページについて、main 状態(before)と現ブランチ状態(after)
を Playwright で撮影し、Designship/site-screenshots に push して、
PR コメントとして貼り付ける。

GitHub には画像をコメントに直接 upload する公式 API が無いため、
このスクリプトは「専用 public リポに push → raw URL を埋め込む」方式を使う。

使い方:
    python3 .claude/scripts/screenshot_diff.py <PR番号>

前提:
    - リポは Designship 組織下の site-* のいずれか
    - gh CLI で認証済み
    - playwright + chromium が install 済み
    - python3 で http.server が動く
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# ---------- 定数 -----------------------------------------------------------

PORT_MAIN_BY_NAME = {
    "site-corporate": 8080,
    "site-conference": 8081,
    "site-do": 8082,
    "site-dialogue": 8083,
    "site-studio": 8084,
}
PORT_PR_OFFSET = 1000   # main = 8081 のとき、worktree = 9081
VIEWPORTS = [("mobile", 375, 812), ("desktop", 1280, 900)]
SCREENSHOTS_REPO = "Designship/site-screenshots"


# ---------- 補助 -----------------------------------------------------------

def run(cmd, cwd=None, check=True, capture=True, env=None):
    """subprocess の薄いラッパ。失敗時は stderr 込みで例外。"""
    res = subprocess.run(
        cmd, cwd=cwd, check=False, text=True,
        capture_output=capture, env=env,
    )
    if check and res.returncode != 0:
        out = (res.stdout or "") + (res.stderr or "")
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{out}")
    return (res.stdout or "").strip() if capture else None


def find_main_repo_root(here: Path) -> Path:
    """worktree から呼ばれても本体側のパスを返す。"""
    common = run(["git", "rev-parse", "--git-common-dir"], cwd=here)
    common_path = Path(common)
    if not common_path.is_absolute():
        common_path = (here / common_path).resolve()
    return common_path.parent


def repo_name(repo_root: Path) -> str:
    return repo_root.name


def site_pages(site_dir: Path) -> list[str]:
    pages = []
    for f in site_dir.rglob("index.html"):
        if "assets" in f.parts or "_nuxt" in f.parts:
            continue
        if ".worktrees" in f.parts or ".baseline" in f.parts:
            continue
        rel = f.parent.relative_to(site_dir)
        pages.append("/" if str(rel) == "." else "/" + str(rel) + "/")
    return sorted(set(pages))


def slug(rel: str) -> str:
    s = rel.strip("/").replace("/", "_")
    return s or "_root"


def changed_pages(repo_root: Path, branch_root: Path) -> tuple[list[str], bool]:
    """
    main..HEAD で変更があったページのリストを返す。
    CSS / JS など全体に影響する変更があれば、第二要素を True にして
    「全ページ撮影モード」を呼び出し側に伝える。
    """
    base = run(["git", "merge-base", "main", "HEAD"], cwd=branch_root)
    diff = run(["git", "diff", "--name-only", base, "HEAD"], cwd=branch_root)
    files = [f for f in diff.splitlines() if f]

    pages: set[str] = set()
    full = False
    for f in files:
        if f.endswith("/index.html"):
            pages.add("/" + f[: -len("index.html")])
        elif f == "index.html":
            pages.add("/")
        elif "_nuxt/" in f and f.endswith(".css"):
            full = True
        elif f.endswith(".css") or f.endswith(".js"):
            full = True
    return sorted(pages), full


# ---------- HTTP server -----------------------------------------------------

@contextmanager
def http_server(directory: Path, port: int):
    """python3 -m http.server を起動して終了時に止める。"""
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", str(port)],
        cwd=directory,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # wait for port to bind
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError(f"http.server failed to come up on :{port}")
        yield port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


# ---------- worktree -------------------------------------------------------

@contextmanager
def main_worktree(main_repo: Path):
    """main をチェックアウトした使い捨て worktree を提供。"""
    parent = main_repo.parent
    wt_dir = parent / ".worktrees" / main_repo.name / ".shot-baseline"
    if wt_dir.exists():
        run(["git", "worktree", "remove", "--force", str(wt_dir)],
            cwd=main_repo, check=False)
    wt_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "worktree", "add", "--force", str(wt_dir), "main"],
        cwd=main_repo)
    try:
        yield wt_dir
    finally:
        run(["git", "worktree", "remove", "--force", str(wt_dir)],
            cwd=main_repo, check=False)


# ---------- screenshot ------------------------------------------------------

async def shoot(page_paths: list[str], port: int, out_dir: Path,
                label: str) -> int:
    """指定ページを mobile/desktop で full-page スクショ。撮影成功数を返す。"""
    from playwright.async_api import async_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    success = 0
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        sem = asyncio.Semaphore(4)

        async def one(rel: str, vp: tuple[str, int, int]):
            nonlocal success
            vname, w, h = vp
            async with sem:
                ctx = await browser.new_context(viewport={"width": w, "height": h})
                p = await ctx.new_page()
                p.set_default_timeout(20000)
                try:
                    await p.goto(f"http://localhost:{port}{rel}",
                                 wait_until="domcontentloaded")
                    await p.wait_for_timeout(800)
                    await p.evaluate(
                        "async () => { for (let y=0;y<document.body.scrollHeight;y+=500){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,80));} window.scrollTo(0,0); }"
                    )
                    await p.wait_for_timeout(400)
                    out = out_dir / f"{vname}_{slug(rel)}.png"
                    await p.screenshot(path=str(out), full_page=True)
                    success += 1
                except Exception as e:
                    print(f"  [{label}] ! {rel} {vname}: {e}")
                finally:
                    await ctx.close()

        await asyncio.gather(*(one(r, vp) for r in page_paths for vp in VIEWPORTS))
        await browser.close()
    return success


# ---------- screenshots repo handling --------------------------------------

def ensure_screenshots_repo(parent: Path) -> Path:
    """site-screenshots を parent/site-screenshots に clone or pull する。"""
    target = parent / "site-screenshots"
    if not target.exists():
        run(["gh", "repo", "clone", SCREENSHOTS_REPO, str(target)])
    else:
        run(["git", "pull", "--ff-only"], cwd=target, check=False)
    return target


def push_screenshots(shots_repo: Path, site: str, pr: int) -> str:
    """commit & push。push 後の base raw URL を返す。"""
    run(["git", "add", "-A"], cwd=shots_repo)
    diff_status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=shots_repo
    ).returncode
    if diff_status == 0:
        # nothing staged
        return ""
    run(["git", "-c", "user.name=Designship Bot",
         "-c", "user.email=bot@design-ship.jp",
         "commit", "-m", f"{site}: PR #{pr} screenshots"], cwd=shots_repo)
    run(["git", "push"], cwd=shots_repo)
    sha = run(["git", "rev-parse", "HEAD"], cwd=shots_repo)
    return f"https://raw.githubusercontent.com/{SCREENSHOTS_REPO}/{sha}/{site}/pr-{pr}"


# ---------- comment formatting ---------------------------------------------

def build_comment(site: str, pr: int, base_url: str,
                  pages: list[str], full_run: bool) -> str:
    header = "## 📸 Before / After スクリーンショット\n\n"
    if not pages:
        return header + "_HTML / CSS / JS の変更がなかったため、スクショは省略しました。_\n"

    rows = ["| ページ | viewport | Before | After |", "|---|---|---|---|"]
    for rel in pages:
        s = slug(rel)
        for vname, _, _ in VIEWPORTS:
            file = f"{vname}_{s}.png"
            before_url = f"{base_url}/before/{file}"
            after_url = f"{base_url}/after/{file}"
            rows.append(
                f"| `{rel}` | {vname} | "
                f"![]({before_url}) | ![]({after_url}) |"
            )
    note = ""
    if full_run:
        note = "\n_共通 CSS/JS の変更を検出したので、全ページを撮影しました。_\n"
    return header + note + "\n".join(rows) + "\n"


# ---------- main -----------------------------------------------------------

def main(argv: list[str]):
    if len(argv) != 2:
        print("usage: screenshot_diff.py <PR番号>")
        sys.exit(2)
    pr_num = int(argv[1])

    here = Path.cwd()
    main_repo = find_main_repo_root(here)
    site = repo_name(main_repo)
    if site not in PORT_MAIN_BY_NAME:
        print(f"!! 不明なリポ名: {site}")
        sys.exit(2)
    main_port = PORT_MAIN_BY_NAME[site]
    pr_port = main_port + PORT_PR_OFFSET

    branch = run(["git", "branch", "--show-current"], cwd=here)
    if branch == "main":
        print("!! main ブランチで実行されています。worktree から実行してください。")
        sys.exit(2)
    print(f"== {site}: PR #{pr_num} on branch '{branch}' ==")

    # 1) 変更ページ判定
    pages, full_run = changed_pages(main_repo, here)
    if full_run or not pages:
        all_p = site_pages(here)
        if full_run:
            print(f"  共通アセット変更を検出 → 全 {len(all_p)} ページを撮影")
            pages = all_p
        elif not pages:
            print("  HTML の変更なし → スクショ省略")

    # 2) スクショ用作業ディレクトリ
    parent = main_repo.parent
    work = parent / ".shot-runs" / f"{site}-pr{pr_num}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    before_dir = work / "before"
    after_dir = work / "after"

    if pages:
        # 3) main を別 worktree に展開して別ポートで起動
        with main_worktree(main_repo) as baseline:
            with http_server(baseline, main_port):
                with http_server(here, pr_port):
                    print("  撮影中: before (main) ...")
                    asyncio.run(shoot(pages, main_port, before_dir, "before"))
                    print("  撮影中: after (PR branch) ...")
                    asyncio.run(shoot(pages, pr_port, after_dir, "after"))

    # 4) site-screenshots に配置
    shots_repo = ensure_screenshots_repo(parent)
    target_dir = shots_repo / site / f"pr-{pr_num}"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    if pages:
        shutil.copytree(before_dir, target_dir / "before", dirs_exist_ok=True)
        shutil.copytree(after_dir, target_dir / "after", dirs_exist_ok=True)
    base_url = push_screenshots(shots_repo, site, pr_num)

    # 5) PR コメント投稿
    comment = build_comment(site, pr_num, base_url or "", pages, full_run)
    if base_url:
        run(["gh", "pr", "comment", str(pr_num), "--body", comment], cwd=main_repo)
        print(f"  ✅ PR #{pr_num} にコメント投稿しました ({len(pages)} ページ × {len(VIEWPORTS)} viewport)")
    else:
        # スクショなし or 既にコメント済み
        run(["gh", "pr", "comment", str(pr_num), "--body", comment], cwd=main_repo)
        print(f"  ℹ️  スクショなしのコメントを投稿しました")

    # 6) 後片付け
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv)
