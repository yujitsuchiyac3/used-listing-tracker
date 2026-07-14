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

    # 報告用サマリ(定期ジョブがこれを読んでチャット報告する)
    import json as _json
    WEEK_JA = ["月", "火", "水", "木", "金", "土", "日"]
    weekday = WEEK_JA[day.weekday()]
    summary = {
        "date": f"{day:%Y-%m-%d}",
        "weekday": weekday,
        "total": total,
        "per_site": {names.get(s, s): len(v) for s, v in new_by_site.items()},
        "errors": list(errors.keys()),
    }
    with open("data/summary.json", "w", encoding="utf-8") as f:
        _json.dump(summary, f, ensure_ascii=False, indent=2)

    # 履歴に記録(日付キーで上書き=同日再実行しても重複しない)
    record_history(summary)
    write_trends()

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


HISTORY_PATH = "data/history.json"
WEEK_ORDER = ["月", "火", "水", "木", "金", "土", "日"]
# 表示順(_site_jobs と同じ並び)
SITE_ORDER = [
    "オルティカ (OrutiKA)",
    "アスカインデックス",
    "Hitech & Facility",
    "オリックス・レンテック 中古機器販売リスト",
    "中古市場(チューコイチ)",
    "計測器ランド リセール",
    "タナカ・トレーディング",
    "中古研究機器.com",
]


def record_history(summary: dict) -> None:
    """日次サマリを data/history.json に日付キーで蓄積(同日再実行は上書き)。"""
    import json
    hist = {}
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, encoding="utf-8") as f:
                hist = json.load(f)
        except Exception:
            hist = {}
    date = summary["date"]
    existing = hist.get(date)
    # 同日2回目以降の実行はスナップショットが進んでいるため新着0になりがち。
    # 既存に新着ありの記録がある日を「0」で上書きしないよう保護する。
    if existing and existing.get("total", 0) > 0 and summary["total"] == 0:
        return
    hist[date] = {
        "weekday": summary.get("weekday", ""),
        "total": summary["total"],
        "per_site": summary["per_site"],
    }
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2, sort_keys=True)


def write_trends() -> None:
    """履歴から「サイト別」の更新傾向を集計し data/trends.html を生成。

    重視するのはサイトごとの更新件数(全体合計ではない)。
    - サイト × 曜日 の新着合計マトリクス
    - サイト別サマリ(観測日数・新着があった日数・新着合計・1日平均)
    """
    import json
    if not os.path.exists(HISTORY_PATH):
        return
    with open(HISTORY_PATH, encoding="utf-8") as f:
        hist = json.load(f)

    sites = list(SITE_ORDER)
    for rec in hist.values():
        for s in rec.get("per_site", {}):
            if s not in sites:
                sites.append(s)

    mat = {s: {w: 0 for w in WEEK_ORDER} for s in sites}
    site_days = {s: 0 for s in sites}
    site_total = {s: 0 for s in sites}
    site_hit = {s: 0 for s in sites}
    for rec in hist.values():
        w = rec.get("weekday")
        ps = rec.get("per_site", {})
        for s in sites:
            if s not in ps:
                continue  # その日は未測定(エラー等)
            n = ps.get(s, 0)
            site_days[s] += 1
            site_total[s] += n
            if n > 0:
                site_hit[s] += 1
            if w in WEEK_ORDER:
                mat[s][w] += n

    head = "".join(f"<th>{w}</th>" for w in WEEK_ORDER)
    mat_rows = []
    for s in sites:
        cells = ""
        for w in WEEK_ORDER:
            v = mat[s][w]
            style = "background:#e6f2ff;" if v > 0 else "color:#bbb;"
            cells += f"<td style='text-align:right;{style}'>{v}</td>"
        mat_rows.append(
            f"<tr><td style='white-space:nowrap;'>{s}</td>{cells}"
            f"<td style='text-align:right;font-weight:bold;'>{site_total[s]}</td></tr>"
        )

    sum_rows = []
    for s in sites:
        d = site_days[s]
        rate = f"{site_hit[s]}/{d}" if d else "-"
        avg = f"{site_total[s]/d:.1f}" if d else "-"
        sum_rows.append(
            f"<tr><td style='white-space:nowrap;'>{s}</td>"
            f"<td style='text-align:center;'>{d}</td>"
            f"<td style='text-align:center;'>{rate}</td>"
            f"<td style='text-align:right;'>{site_total[s]}</td>"
            f"<td style='text-align:right;'>{avg}</td></tr>"
        )

    html = f"""<!doctype html><meta charset="utf-8">
<title>サイト別 更新傾向</title>
<div style="font-family:Hiragino Sans,Meiryo,sans-serif;max-width:820px;margin:24px auto;color:#1a1a1a;">
<h1 style="font-size:20px;">サイト別 更新傾向</h1>
<p style="color:#666;font-size:13px;">観測 {len(hist)} 日ぶん。数字は各セルの新着合計です。データが増えるほど精度が上がります。</p>

<h2 style="font-size:15px;">サイト × 曜日(新着合計)</h2>
<div style="overflow-x:auto;">
<table style="border-collapse:collapse;font-size:13px;" border="1" cellpadding="6">
<tr style="background:#f0f4f8;"><th style="text-align:left;">サイト</th>{head}<th>合計</th></tr>
{''.join(mat_rows)}
</table>
</div>

<h2 style="font-size:15px;margin-top:24px;">サイト別サマリ</h2>
<table style="border-collapse:collapse;font-size:13px;" border="1" cellpadding="6">
<tr style="background:#f0f4f8;"><th style="text-align:left;">サイト</th><th>観測日数</th><th>新着あり日</th><th>新着合計</th><th>1日平均</th></tr>
{''.join(sum_rows)}
</table>
<p style="margin-top:16px;"><a href="index.html">← 一覧へ戻る</a></p>
</div>"""
    with open("data/trends.html", "w", encoding="utf-8") as f:
        f.write(html)


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
<p><a href="trends.html" style="font-size:14px;color:#2b6cb0;">📊 更新傾向(曜日別)を見る</a></p>
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
