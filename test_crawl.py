"""1サイト分の単発クロール動作確認用スクリプト。

使い方: python3 test_crawl.py [--no-enrich] [--limit N]
取得結果を見やすく表示し、JSON でも data/ に保存する。
"""
import argparse
import json
import sys

from scrapers.orutika import OrutikaScraper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-enrich", action="store_true", help="詳細ページを取得しない")
    ap.add_argument("--limit", type=int, default=0, help="先頭N件のみ詳細取得して表示")
    ap.add_argument("--max-pages", type=int, default=1, help="一覧の取得ページ数")
    args = ap.parse_args()

    scraper = OrutikaScraper(request_interval=1.0)

    # まず一覧だけ取得 (enrich しない) してから limit 件だけ詳細取得する
    listings = scraper.fetch_listings(enrich=False, max_pages=args.max_pages)
    print(f"[{scraper.name}] 一覧取得: {len(listings)} 件\n")

    if not args.no_enrich:
        targets = listings if args.limit == 0 else listings[: args.limit]
        for item in targets:
            try:
                scraper._enrich_detail(item)
            except Exception as e:
                print(f"  詳細取得失敗 {item.uid}: {e}", file=sys.stderr)

    for i, it in enumerate(listings, 1):
        print(f"--- {i}/{len(listings)} ---")
        print(f"  管理番号 : {it.uid}")
        print(f"  メーカー : {it.maker}")
        print(f"  型番     : {it.model}")
        print(f"  名称     : {it.name}")
        print(f"  スペック : {it.spec[:60]}")
        print(f"  価格     : {it.price} ({it.price_value})")
        print(f"  状態     : {it.condition}")
        print(f"  NEW      : {it.is_new_badge}")
        print(f"  画像     : {it.image_url}")
        print(f"  URL      : {it.url}")

    out = [vars(it) for it in listings]
    with open("data/orutika_sample.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nJSON 保存: data/orutika_sample.json ({len(out)} 件)")


if __name__ == "__main__":
    main()
