"""統合ランナー。

全サイトを巡回 → 前回スナップショットとの差分(新着)を抽出 →
新着のみ詳細補完 → HTML生成(最新版・日付別アーカイブ・インデックス) →
スナップショット更新。既定ではメール送信しない(GitHub上でHTMLを生成・公開)。

使い方:
  python3 main.py             # 収集してHTML生成(data/latest.html 等)
  python3 main.py --force-all # 差分でなく現在の全件を出力(テスト用)
  python3 main.py --send      # HTML生成に加えてメール送信も行う(任意, SMTP環境変数)
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
import traceback
from typing import Callable, List

from scrapers.base import Listing
from scrapers.orutika import OrutikaScraper
from scrapers.askindex import AskindexScraper
from scrapers.hitechfacility import HitechFacilityScraper
from scrapers.orixrentec import OrixRentecScraper
from scrapers.chukoichi import ChukoichiScraper
from scrapers.keisokuki import KeisokukiScraper
from scrapers.tanaka3915 import Tanaka3915Scraper
from scrapers.usedlab import UsedLabScraper

from core import notifier, storage


# (scraper, list取得関数, 新着1件を詳細補完する関数 or None)
def _site_jobs():
    orutika = OrutikaScraper()
    usedlab = UsedLabScraper()
    askindex = AskindexScraper()
    hitech = HitechFacilityScraper()
    orix = OrixRentecScraper()
    chukoichi = ChukoichiScraper()
    keisokuki = KeisokukiScraper()
    tanaka = Tanaka3915Scraper()
    return [
        (orutika, lambda: orutika.fetch_listings(enrich=False), orutika._enrich_detail),
        (askindex, askindex.fetch_listings, None),
        (hitech, hitech.fetch_listings, None),
        (orix, orix.fetch_listings, None),
        (chukoichi, chukoichi.fetch_listings, None),
        (keisokuki, keisokuki.fetch_listings, None),
        (tanaka, tanaka.fetch_listings, None),
        (usedlab, lambda: usedlab.fetch_listings(enrich=False), usedlab._enrich_detail),
    ]


def _fetch_with_retry(fetch: Callable[[], List[Listing]], attempts: int = 3) -> List[Listing]:
    import time
    last = None
    for i in range(attempts):
        try:
            return fetch()
        except Exception as e:  # 一時的な503等に備えてリトライ
            last = e
            time.sleep(2 * (i + 1))
    raise last


def run(send: bool = False, force_all: bool = False) -> int:
    day = datetime.date.today()
    snap = storage.Snapshot()
    prev_state = snap.load()
    new_state = dict(prev_state)

    names = {}
    new_by_site = {}
    errors = {}

    for scraper, fetch, enrich in _site_jobs():
        site = scraper.site
        names[site] = scraper.name
        try:
            listings = _fetch_with_retry(fetch)
        except Exception as e:
            errors[site] = f"{type(e).__name__}: {e}"
            print(f"[ERROR] {site}: {e}", file=sys.stderr)
            traceback.print_exc()
            continue

        # 今回分でスナップショット更新(初回はベースライン化)
        new_state[site] = storage.build_state_for_site(listings)

        if force_all:
            new_items = listings
        else:
            new_items = storage.diff_new(prev_state, site, listings)

        # 新着のみ詳細補完
        if enrich:
            for it in new_items:
                try:
                    enrich(it)
                except Exception:
                    pass

        new_by_site[site] = new_items
        print(f"{site}: 取得{len(listings)}件 / 新着{len(new_items)}件"
              + (f" [ERR]" if site in errors else ""))

    total = sum(len(v) for v in new_by_site.values())
    subject = notifier.build_subject(new_by_site, day)
    html = notifier.build_html(new_by_site, names, day)
    text = notifier.build_text(new_by_site, names, day)

    # HTML を出力(最新版・日付別アーカイブ)
    os.makedirs("data/archive", exist_ok=True)
    with open("data/latest.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open(f"data/archive/{day:%Y-%m-%d}.html", "w", encoding="utf-8") as f:
        f.write(html)
    write_index()

    print(f"\n新着合計: {total}件  件名: {subject}")
    if errors:
        print(f"取得失敗サイト: {', '.join(errors)}")

    if send:
        from core import mailer
        mailer.send(subject, html, text)
        print("メール送信しました")
    else:
        print("HTML を data/latest.html と data/archive/ に出力しました")

    snap.save(new_state)
    return 0


def write_index() -> None:
    """data/index.html を生成。最新版と日付別アーカイブへのリンク一覧。"""
    import glob
    files = sorted(glob.glob("data/archive/*.html"), reverse=True)
    rows = []
    for path in files:
        date = os.path.splitext(os.path.basename(path))[0]
        rows.append(
            f'<li><a href="archive/{date}.html">{date}</a></li>'
        )
    body = "\n".join(rows) or "<li>まだ履歴がありません</li>"
    html = f"""<!doctype html><meta charset="utf-8">
<title>中古計測器 新着まとめ</title>
<div style="font-family:Hiragino Sans,Meiryo,sans-serif;max-width:680px;margin:24px auto;color:#1a1a1a;">
<h1 style="font-size:20px;">中古計測器 新着まとめ</h1>
<p><a href="latest.html" style="font-size:16px;color:#2b6cb0;">▶ 最新の新着を見る</a></p>
<h2 style="font-size:15px;border-bottom:1px solid #ccc;padding-bottom:4px;">日付別アーカイブ</h2>
<ul style="line-height:1.9;">
{body}
</ul>
</div>"""
    with open("data/index.html", "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="HTML生成に加えてメール送信も行う(SMTP環境変数が必要)")
    ap.add_argument("--force-all", action="store_true", help="差分でなく現在の全件を出力")
    args = ap.parse_args()
    sys.exit(run(send=args.send, force_all=args.force_all))
