"""統合ランナー。

全サイトを巡回 → 前回スナップショットとの差分(新着)を抽出 →
新着のみ詳細補完 → メールHTML生成 → 送信(または dry-run でファイル出力) →
スナップショット更新。

使い方:
  python3 main.py            # 収集して送信(SMTP環境変数が必要)
  python3 main.py --dry-run  # 送信せず data/latest_email.html に出力
  python3 main.py --force-all# 差分でなく現在の全件をメール化(テスト用)
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


def run(dry_run: bool = False, force_all: bool = False) -> int:
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

    # プレビュー/アーカイブ用に常にファイル出力
    os.makedirs("data/archive", exist_ok=True)
    with open("data/latest_email.html", "w", encoding="utf-8") as f:
        f.write(html)
    with open(f"data/archive/{day:%Y-%m-%d}.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n新着合計: {total}件  件名: {subject}")
    if errors:
        print(f"取得失敗サイト: {', '.join(errors)}")

    if dry_run:
        print("dry-run: 送信せず data/latest_email.html に出力しました")
    else:
        from core import mailer
        mailer.send(subject, html, text)
        print("メール送信しました")

    snap.save(new_state)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="送信せずHTML出力のみ")
    ap.add_argument("--force-all", action="store_true", help="差分でなく全件をメール化")
    args = ap.parse_args()
    sys.exit(run(dry_run=args.dry_run, force_all=args.force_all))
