"""フォロー(watch.html)の「今日の増分」をテキストで出力する。

定期通知ジョブ用。data/watch.html を前回コミット時点のものと突き合わせ、
新しく載った品だけを報告する。増分が無ければ何も出力せず終了コード1を返す
(= 通知不要のサイン)。

  python3 tools/watch_report.py           # 増分のみ
  python3 tools/watch_report.py --all     # 現在のフォロー該当を全部出す

判定は URL 単位。日次巡回が付ける NEW バッジ(その日の新着)も併記する。
"""
from __future__ import annotations

import html
import re
import subprocess
import sys

WATCH_PATH = "data/watch.html"

CARD_RE = re.compile(r'<div class="card([^"]*)">(.*?)</div></div>', re.S)
SEC_RE = re.compile(r'<div class="sec"><h2>★ (.*?)</h2>')
LINK_RE = re.compile(r'<div class="model"><a href="([^"]+)">(.*?)</a></div>', re.S)
MAKER_RE = re.compile(r'<div class="maker">(.*?)</div>', re.S)
PRICE_RE = re.compile(r'<div class="price">(.*?)</div>', re.S)


def _text(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s)).strip()


def parse(page: str) -> list[dict]:
    """watch.html を [{group, url, title, maker, price, is_new}] に分解。"""
    items = []
    # セクション見出しで区切り、各ブロック内のカードをそのグループに属させる
    marks = [(m.start(), _text(m.group(1))) for m in SEC_RE.finditer(page)]
    for i, (pos, label) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(page)
        for cls, body in CARD_RE.findall(page[pos:end]):
            link = LINK_RE.search(body)
            if not link:
                continue
            maker = MAKER_RE.search(body)
            price = PRICE_RE.search(body)
            items.append({
                "group": label,
                "url": html.unescape(link.group(1)),
                "title": _text(link.group(2)),
                "maker": _text(maker.group(1)) if maker else "",
                "price": _text(price.group(1)) if price else "",
                "is_new": "isnew" in cls,
            })
    return items


def previous_page() -> str | None:
    """data/watch.html を最後に変更したコミットの、ひとつ前の版を取り出す。"""
    try:
        revs = subprocess.run(
            ["git", "log", "-2", "--format=%H", "--", WATCH_PATH],
            capture_output=True, text=True, check=True).stdout.split()
        if len(revs) < 2:
            return None
        return subprocess.run(["git", "show", f"{revs[1]}:{WATCH_PATH}"],
                              capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError:
        return None


def fmt(items: list[dict]) -> str:
    lines = []
    group = None
    for it in items:
        if it["group"] != group:
            group = it["group"]
            lines.append(f"\n★ {group}")
        tag = " [本日新着]" if it["is_new"] else ""
        price = f" / {it['price']}" if it["price"] else ""
        lines.append(f"- {it['maker']} {it['title']}{price}{tag}\n  {it['url']}")
    return "\n".join(lines).strip()


def main(argv: list[str]) -> int:
    with open(WATCH_PATH, encoding="utf-8") as f:
        current = parse(f.read())

    if "--all" in argv:
        print(f"フォロー該当 {len(current)}件")
        print(fmt(current))
        return 0

    prev_page = previous_page()
    if prev_page is None:
        # 比較対象が無い(初回)。差分扱いにはせず通知しない。
        return 1
    known = {it["url"] for it in parse(prev_page)}
    added = [it for it in current if it["url"] not in known]
    if not added:
        return 1
    print(f"フォローに {len(added)}件 追加されました(現在の該当 {len(current)}件)")
    print(fmt(added))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
